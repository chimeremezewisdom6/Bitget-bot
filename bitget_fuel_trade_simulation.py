"""Read-only fuel-conditioned breakout simulation with account fees and live depth proxy."""
import asyncio,base64,csv,hashlib,hmac,json,math,os,statistics,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import aiohttp
BASE="https://api.bitget.com";CAT="USDT-FUTURES";M=60000;H=240;N=float(os.getenv("BITGET_RESEARCH_NOTIONAL_USDT","1000"));SL=float(os.getenv("BITGET_RESEARCH_STOP_PCT","0.5"));TP=float(os.getenv("BITGET_RESEARCH_TARGET_PCT","1.5"))
R=Path(__file__).resolve().parent/"reports/daily_research";EV=R/"bitget_14d_trend_fuel_events.jsonl";DV=R/"bitget_14d_derivatives_fuel_events.jsonl"
def num(x,d=None):
 try:
  v=float(x);return v if math.isfinite(v) else d
 except (TypeError,ValueError):return d
def creds():
 def p(*ks):return next((os.getenv(k,"").strip() for k in ks if os.getenv(k,"").strip()),"")
 return p("BITGET_API_KEY","BITGET_KEY"),p("BITGET_API_SECRET","BITGET_SECRET_KEY","BITGET_SECRET"),p("BITGET_API_PASSPHRASE","BITGET_PASSPHRASE","BITGET_API_PASSWORD","BITGET_PASSWORD")
def headers(path,params):
 k,s,p=creds()
 if not all((k,s,p)):raise RuntimeError("Missing Bitget GitHub Secrets; credentials are never printed.")
 q=urlencode(sorted(params.items()));ts=str(int(time.time()*1000));sig=base64.b64encode(hmac.new(s.encode(),(ts+"GET"+path+("?"+q if q else "")).encode(),hashlib.sha256).digest()).decode()
 return {"ACCESS-KEY":k,"ACCESS-SIGN":sig,"ACCESS-TIMESTAMP":ts,"ACCESS-PASSPHRASE":p},q
class Gate:
 def __init__(self,rate=14):self.delay=1/rate;self.last=0;self.lock=asyncio.Lock()
 async def wait(self):
  async with self.lock:
   d=self.delay-(time.monotonic()-self.last)
   if d>0:await asyncio.sleep(d)
   self.last=time.monotonic()
async def get(ss,g,path,params=None,auth=False):
 params=params or {};h=None;url=BASE+path
 if auth:h,q=headers(path,params);url+=("?"+q if q else "");params=None
 err=None
 for i in range(6):
  await g.wait()
  try:
   async with ss.get(url,params=params,headers=h) as r:
    if r.status==429 or r.status>=500:raise RuntimeError("HTTP "+str(r.status))
    r.raise_for_status();z=await r.json()
    if z.get("code")!="00000":raise RuntimeError(str(z.get("code"))+" "+str(z.get("msg")))
    return z.get("data")
  except Exception as e:
   err=e
   if i<5:await asyncio.sleep(min(20,1.5*2**i))
 raise RuntimeError(str(err))
def fee_map(data):
 rows=data if isinstance(data,list) else next((data.get(k) for k in ("list","resultList","data") if isinstance(data,dict) and isinstance(data.get(k),list)),[])
 out={}
 for x in rows or []:
  if not isinstance(x,dict):continue
  s=x.get("symbol") or x.get("instId")
  v=next((num(x.get(k)) for k in ("takerFeeRate","takerFee","taker_fee_rate") if num(x.get(k)) is not None),None)
  if s and v is not None:out[s]=v
 return out
def parse(raw):
 d={}
 for x in raw or []:
  try:d[int(x[0])]={"ts":int(x[0]),"o":num(x[1],0),"h":num(x[2],0),"l":num(x[3],0),"c":num(x[4],0)}
  except Exception:pass
 return [d[k] for k in sorted(d)]
async def candles(ss,g,sem,sym,start,end):
 async with sem:
  raw=[];t=start
  while t<end:
   stop=min(end,t+950*M);p={"category":CAT,"symbol":sym,"interval":"1m","startTime":str(t),"endTime":str(stop-1),"limit":"1000","type":"market"}
   raw+=await get(ss,g,"/api/v3/market/candles",p) or [];t=stop
  return sym,[x for x in parse(raw) if start<=x["ts"]<end]
def vwap(levels):
 left=N;cost=qty=0
 for p,q in levels or []:
  p=num(p);q=num(q)
  if not p or not q or p<=0 or q<=0:continue
  take=min(left,p*q);cost+=take;qty+=take/p;left-=take
  if left<=1e-7:break
 return cost/qty if qty and left<=max(.01,N*.0001) else None
async def book(ss,g,sem,sym):
 async with sem:
  try:
   d=await get(ss,g,"/api/v3/market/orderbook",{"category":CAT,"symbol":sym,"limit":"50"})
   a=d.get("a",[]);b=d.get("b",[]);bid=num(b[0][0]);ask=num(a[0][0]);mid=(bid+ask)/2
   buy=vwap(a);sell=vwap(b)
   if not buy or not sell:return sym,{"error":"insufficient depth"}
   return sym,{"ts":num(d.get("ts")),"spread_bps":(ask-bid)/mid*1e4,"buy_slip":(buy/mid-1)*1e4,"sell_slip":(1-sell/mid)*1e4}
  except Exception as e:return sym,{"error":str(e)[:160]}
def features(e,d):
 p=e.get("pre_breakout_features") or {};side=e.get("direction")
 def f(m,k):return num((p.get(str(m)) or {}).get(k))
 t5=f(5,"turnover_vs_pre60");t10=f(10,"turnover_vs_pre60");c5=f(5,"directional_candle_share");c10=f(10,"directional_candle_share");eff=f(5,"path_efficiency")
 oi=num((d or {}).get("open_interest_change_pct"));imb=num((d or {}).get("taker_imbalance"))
 aligned=imb is not None and (imb>.10 if side=="LONG" else imb<-.10)
 flags={"turnover_1_5x":t5 is not None and t5>=1.5,"turnover_2x":t5 is not None and t5>=2,
 "directional_60pct":c5 is not None and c5>=.6,"efficient_035":eff is not None and eff>=.35,
 "turnover_10m_1_5x":t10 is not None and t10>=1.5,"directional_10m_60pct":c10 is not None and c10>=.6,
 "oi_rising":oi is not None and oi>0,"taker_aligned":aligned}
 flags["price_volume_fuel"]=all(flags[k] for k in ("turnover_1_5x","directional_60pct","efficient_035"))
 flags["strong_price_volume_fuel"]=all(flags[k] for k in ("turnover_2x","turnover_10m_1_5x","directional_60pct","directional_10m_60pct","efficient_035"))
 flags["derivatives_confirmed_fuel"]=flags["strong_price_volume_fuel"] and flags["oi_rising"] and flags["taker_aligned"]
 vals={"turnover_5m_vs_pre60":t5,"turnover_10m_vs_pre60":t10,"directional_share_5m":c5,"directional_share_10m":c10,"path_efficiency_5m":eff,"oi_change_pct":oi,"taker_imbalance":imb}
 return flags,vals
def sim(e,rows,fee,b):
 idx={x["ts"]:i for i,x in enumerate(rows)}.get(int(e["timestamp_ms"]))
 if idx is None or idx+H>=len(rows):return None
 entbar=rows[idx+1];entry=entbar["o"];side=e["direction"]
 if not entry:return None
 stop=entry*(1-SL/100) if side=="LONG" else entry*(1+SL/100);target=entry*(1+TP/100) if side=="LONG" else entry*(1-TP/100)
 exitp=exitts=reason=None
 for bar in rows[idx+1:idx+H+1]:
  sh=bar["l"]<=stop if side=="LONG" else bar["h"]>=stop
  th=bar["h"]>=target if side=="LONG" else bar["l"]<=target
  if sh:exitp=stop;exitts=bar["ts"];reason="STOP";break
  if th:exitp=target;exitts=bar["ts"];reason="TARGET";break
 if exitp is None:bar=rows[idx+H];exitp=bar["c"];exitts=bar["ts"];reason="TIME_240M"
 gross=((exitp/entry)-1)*100 if side=="LONG" else ((entry/exitp)-1)*100
 fee_bps=fee*2*10000 if fee is not None else None
 if b and not b.get("error"):
  ent=b["buy_slip"] if side=="LONG" else b["sell_slip"];ex=b["sell_slip"] if side=="LONG" else b["buy_slip"];slip=ent+ex
 else:ent=ex=slip=None
 net=gross*100-fee_bps-slip if fee_bps is not None and slip is not None else None
 return {"symbol":e["symbol"],"direction":side,"signal_time_utc":datetime.fromtimestamp(int(e["timestamp_ms"])/1000,timezone.utc).isoformat(),"entry_time_utc":datetime.fromtimestamp(entbar["ts"]/1000,timezone.utc).isoformat(),"exit_time_utc":datetime.fromtimestamp(exitts/1000,timezone.utc).isoformat(),"entry_price":entry,"exit_price":exitp,"exit_reason":reason,"duration_minutes":(exitts-entbar["ts"])/M,"gross_return_pct":gross,"round_trip_fee_bps":fee_bps,"entry_slippage_bps_proxy":ent,"exit_slippage_bps_proxy":ex,"round_trip_slippage_bps_proxy":slip,"net_return_bps_estimated":net,"net_pnl_usdt_estimated":N*net/1e4 if net is not None else None,"fuel_flags":None,"fuel_values":None}
def stats(rows):
 s=[x for x in rows if x["net_return_bps_estimated"] is not None];w=[x for x in s if x["net_return_bps_estimated"]>0];l=[x for x in s if x["net_return_bps_estimated"]<0]
 gp=sum(x["net_pnl_usdt_estimated"] for x in w);gl=abs(sum(x["net_pnl_usdt_estimated"] for x in l))
 aw=statistics.mean([x["net_return_bps_estimated"] for x in w]) if w else None;al=abs(statistics.mean([x["net_return_bps_estimated"] for x in l])) if l else None
 return {"occurrences":len(rows),"scored":len(s),"wins":len(w),"losses":len(l),"win_rate_pct":100*len(w)/len(s) if s else None,"profit_factor":gp/gl if gl else None,"net_pnl_usdt":sum(x["net_pnl_usdt_estimated"] for x in s),"avg_win_to_loss":aw/al if aw is not None and al else None,"avg_win_bps":aw,"avg_loss_bps":al,"median_duration_minutes":statistics.median([x["duration_minutes"] for x in rows]) if rows else None,"stop_exits":sum(x["exit_reason"]=="STOP" for x in rows),"target_exits":sum(x["exit_reason"]=="TARGET" for x in rows),"time_exits":sum(x["exit_reason"]=="TIME_240M" for x in rows)}
async def main():
 R.mkdir(parents=True,exist_ok=True)
 if not EV.exists():raise RuntimeError("Missing 14-day event file.")
 events=[json.loads(x) for x in EV.read_text().splitlines() if x.strip()]
 if not events:raise RuntimeError("No breakout events.")
 ds=[json.loads(x) for x in DV.read_text().splitlines() if x.strip()] if DV.exists() else []
 dm={(x.get("symbol"),int(x.get("timestamp_ms") or 0)):x for x in ds}
 syms=sorted({e["symbol"] for e in events});end=int(time.time()*1000)//M*M;start=end-14*1440*M;g=Gate()
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=55),connector=aiohttp.TCPConnector(limit=24)) as ss:
  acct=await get(ss,g,"/api/v3/account/info",auth=True);perm=acct.get("permType","unknown") if isinstance(acct,dict) else "unknown"
  fees=fee_map(await get(ss,g,"/api/v3/account/all-fee-rate",{"category":CAT},auth=True))
  sem=asyncio.Semaphore(10);cs=await asyncio.gather(*(candles(ss,g,sem,s,start,end) for s in syms))
  bs=await asyncio.gather(*(book(ss,g,sem,s) for s in syms))
 cm=dict(cs);bm=dict(bs);trades=[];annotated=[];sets={"ALL_BREAKOUTS":[],"TURNOVER_1_5X":[],"PRICE_VOLUME_FUEL":[],"STRONG_PRICE_VOLUME_FUEL":[],"DERIVATIVES_CONFIRMED_FUEL":[]}
 for e in events:
  d=dm.get((e.get("symbol"),int(e.get("timestamp_ms") or 0)));fl,vals=features(e,d)
  t=sim(e,cm.get(e["symbol"],[]),fees.get(e["symbol"]),bm.get(e["symbol"]))
  row={**e,"fuel_flags":fl,"fuel_values":vals,"derivatives_observed":bool(d and (d.get("open_interest_change_pct") is not None or d.get("taker_imbalance") is not None))}
  annotated.append(row)
  if t:
   t["fuel_flags"]=fl;t["fuel_values"]=vals;trades.append(t)
   sets["ALL_BREAKOUTS"].append(t)
   if fl["turnover_1_5x"]:sets["TURNOVER_1_5X"].append(t)
   if fl["price_volume_fuel"]:sets["PRICE_VOLUME_FUEL"].append(t)
   if fl["strong_price_volume_fuel"]:sets["STRONG_PRICE_VOLUME_FUEL"].append(t)
   if fl["derivatives_confirmed_fuel"]:sets["DERIVATIVES_CONFIRMED_FUEL"].append(t)
 cut=start+9*24*1440*M;comb={}
 for name,rows in sets.items():
  tr=[x for x in rows if int(datetime.fromisoformat(x["signal_time_utc"]).timestamp()*1000)<cut];te=[x for x in rows if int(datetime.fromisoformat(x["signal_time_utc"]).timestamp()*1000)>=cut]
  comb[name]={"all_14d":stats(rows),"train_first_9d":stats(tr),"out_of_sample_last_5d":stats(te)}
 percoin={s:stats([t for t in trades if t["symbol"]==s]) for s in syms}
 occ={k:sum(bool(x["fuel_flags"].get(k)) for x in annotated) for k in ("turnover_1_5x","turnover_2x","directional_60pct","efficient_035","price_volume_fuel","strong_price_volume_fuel","derivatives_confirmed_fuel")}
 coin_occ={k:{s:sum(bool(x["fuel_flags"].get(k)) for x in annotated if x["symbol"]==s) for s in syms if any(bool(x["fuel_flags"].get(k)) for x in annotated if x["symbol"]==s)} for k in occ}
 summary={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"authenticated_read":"success","account_permission_type":perm,"markets":len(syms),"breakout_events":len(events),"notional_usdt_per_trade":N,"stop_loss_pct":SL,"take_profit_pct":TP,"max_hold_minutes":H,"entry":"next 1m candle open after breakout candle closes","exit":"first stop/target touch; stop wins same-candle ambiguity; otherwise 240m close","fee_schedule_symbols":len(fees),"symbols_missing_fee":[s for s in syms if s not in fees],"fuel_occurrences":occ,"fuel_coin_occurrences":coin_occ,"combinations":comb,"per_coin":percoin,"derivatives_events_with_any_data":sum(x["derivatives_observed"] for x in annotated),"book_errors":{s:v.get("error") for s,v in bm.items() if v.get("error")},"cost_model":"Current account taker fees plus current 50-level book VWAP impact proxy per coin at fixed notional; not historical depth/slippage.","limitations":["Coin universe is inherited from top-200 currently active USDT perpetuals, not every historical/delisted contract.","Current orderbook snapshot is not historical orderbook; slippage is a per-coin current-depth proxy.","Current fee tier is applied retrospectively; historical fee tier may differ.","Funding cashflows, latency, queue position, market impact beyond visible depth and overlapping portfolio positions are not modeled.","OI/taker data only count when a timestamped event enrichment exists; missing values are not inferred.","14-day sample and 5-day out-of-sample are exploratory, not statistically conclusive.","No orders are placed; this is read-only research."]}
 (R/"bitget_fuel_trade_simulation_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (R/"bitget_fuel_trade_simulation_events.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in annotated))
 with (R/"bitget_fuel_trade_simulation_trades.csv").open("w",newline="",encoding="utf-8") as f:
  cols=["symbol","direction","signal_time_utc","entry_time_utc","exit_time_utc","entry_price","exit_price","exit_reason","duration_minutes","gross_return_pct","round_trip_fee_bps","round_trip_slippage_bps_proxy","net_return_bps_estimated","net_pnl_usdt_estimated","fuel_flags","fuel_values"]
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for t in trades:w.writerow({k:json.dumps(t.get(k)) if k in ("fuel_flags","fuel_values") else t.get(k) for k in cols})
 lines=["# Bitget fuel-conditioned trade simulation","",f"Generated: {summary['generated_at_utc']}","Markets: "+str(len(syms))+"; breakout events: "+str(len(events))+"; simulated trades: "+str(len(trades)),f"Authenticated account read: success; permission type: {perm}; fee symbols: {len(fees)}",f"Fixed notional: {N} USDT; stop: {SL}%; target: {TP}%; maximum hold: {H} minutes","","| Fuel combination | Occurrences | Win % | Profit factor | Avg win/loss | Net USDT | Median duration m | OOS win % | OOS PF | OOS net USDT |","|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
 for k,v in comb.items():
  a=v["all_14d"];o=v["out_of_sample_last_5d"]
  def f(x):return "n/a" if x is None else str(round(x,3))
  lines.append(f"| {k} | {a['occurrences']} | {f(a['win_rate_pct'])} | {f(a['profit_factor'])} | {f(a['avg_win_to_loss'])} | {f(a['net_pnl_usdt'])} | {f(a['median_duration_minutes'])} | {f(o['win_rate_pct'])} | {f(o['profit_factor'])} | {f(o['net_pnl_usdt'])} |")
 lines += ["","## Fuel occurrences by coin"]
 for k,v in coin_occ.items():
  top=sorted(v.items(),key=lambda x:(-x[1],x[0]))[:30]
  lines.append("- "+k+": "+str(occ[k])+" occurrences; "+", ".join(s+" ("+str(n)+")" for s,n in top))
 lines += ["","## Per-coin net outcomes","| Coin | Trades | Win % | PF | Net USDT | Median duration m |","|---|---:|---:|---:|---:|---:|"]
 for s,v in sorted(percoin.items(),key=lambda x:(-(x[1]["net_pnl_usdt"] if x[1]["net_pnl_usdt"] is not None else -1e99),x[0])):
  lines.append(f"| {s} | {v['occurrences']} | {v['win_rate_pct']} | {v['profit_factor']} | {v['net_pnl_usdt']} | {v['median_duration_minutes']} |")
 lines += ["","## Execution model","- Entry is next 1m open after breakout candle closes; exit at first stop/target, otherwise 240m close.","- Same-candle stop/target ambiguity is resolved against the trade (stop first).","- Fees use authenticated current account taker rates, round trip.","- Slippage uses current 50-level orderbook VWAP at fixed notional; it is not historical slippage.","- Funding, latency, queue position and portfolio overlap are excluded.","","## Limitations"]+["- "+x for x in summary["limitations"]]
 (R/"bitget_fuel_trade_simulation_report.md").write_text("\n".join(lines)+"\n")
 print(json.dumps({"status":"complete","authenticated":True,"markets":len(syms),"events":len(events),"trades":len(trades),"fuel_occurrences":occ,"results":comb},indent=2))
if __name__=="__main__":asyncio.run(main())
