"""Independent Binance USD-M Futures 14-day validation. Public endpoints only; no key or trading."""
import asyncio,json,math,statistics,time
from datetime import datetime,timezone
from pathlib import Path
import aiohttp
BASE="https://fapi.binance.com";MIN=60000;DAYS=14;PRE=60;H=120;W=(1,3,5,10,15,30,60)
OUT=Path(__file__).resolve().parent/"reports/daily_research"
def med(a):
 a=[x for x in a if x is not None and math.isfinite(x)]
 return round(statistics.median(a),6) if a else None
def dp(a,b,s):
 if not a:return None
 x=(b/a-1)*100
 return x if s=="LONG" else -x
def feat(rows,s,base):
 if not rows:return {}
 move=dp(rows[0][1],rows[-1][4],s);path=sum(abs((r[4]/r[1]-1)*100) for r in rows if r[1])
 d=sum(r[4]>r[1] if s=="LONG" else r[4]<r[1] for r in rows)
 buy=sum(r[10] for r in rows);sell=sum(max(0,r[7]-r[10]) for r in rows)
 return {"directional_return_pct":round(move,6) if move is not None else None,
 "directional_candle_share":round(d/len(rows),6),"path_efficiency":round(abs(move)/path,6) if move is not None and path else None,
 "turnover_vs_pre60":round(statistics.mean(r[7] for r in rows)/base,6) if base else None,
 "taker_buy_sell_quote_ratio":round(buy/sell,6) if sell else None}
async def get(ss,sem,path,params=None):
 async with sem:
  err=None
  for i in range(6):
   try:
    async with ss.get(BASE+path,params=params) as r:
     if r.status in (418,429) or r.status>=500:raise RuntimeError("HTTP "+str(r.status))
     r.raise_for_status();return await r.json()
   except Exception as e:
    err=e
    if i<5:await asyncio.sleep(min(20,1.5*2**i))
  raise RuntimeError(str(err))
async def fetch(ss,sem,sym,start,end):
 rows=[];t=start;errors=[]
 while t<end:
  try:
   batch=await get(ss,sem,"/fapi/v1/klines",{"symbol":sym,"interval":"1m","startTime":t,"endTime":end-1,"limit":1500})
   if not batch:break
   rows.extend(batch);nxt=int(batch[-1][0])+MIN
   if nxt<=t:break
   t=nxt
   if len(batch)<1500:break
  except Exception as e:errors.append(str(e)[:160]);break
 clean={}
 for r in rows:
  try:
   ts=int(r[0])
   if start<=ts<end:clean[ts]=[ts,float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5]),int(r[6]),float(r[7]),int(r[8]),float(r[9]),float(r[10])]
  except (ValueError,TypeError,IndexError):pass
 return sym,[clean[k] for k in sorted(clean)],errors
def scan(sym,rs):
 out=[];last=-10**9
 for i in range(PRE,len(rs)-H):
  if i-last<H:continue
  z=rs[i-PRE:i+H]
  if any(z[j][0]-z[j-1][0]!=MIN for j in range(1,len(z))):continue
  pre,fut,c=rs[i-PRE:i],rs[i:i+H],rs[i];hi=max(x[2] for x in pre);lo=min(x[3] for x in pre)
  if c[4]>hi:s,b="LONG",hi
  elif c[4]<lo:s,b="SHORT",lo
  else:continue
  last=i;final=dp(c[1],fut[-1][4],s);early=dp(fut[0][1],fut[9][4],s)
  ratio=final/abs(early) if early is not None and abs(early)>1e-9 else None
  holds=[x[4]>b if s=="LONG" else x[4]<b for x in fut]
  strict=all(holds);tol=sum(holds)>=117
  gradual=bool(strict and final is not None and final>=4 and ratio is not None and ratio>=4)
  tg=bool(tol and final is not None and final>=4 and ratio is not None and ratio>=4)
  spike=bool(final is not None and final>=4 and ratio is not None and ratio<4)
  base=statistics.mean(x[7] for x in pre);pf={str(w):feat(pre[-w:],s,base) for w in W};qf={str(w):feat(fut[:w],s,base) for w in W}
  hour=fut[:60];colors=["GREEN" if x[4]>x[1] else "RED" if x[4]<x[1] else "DOJI" for x in hour]
  out.append({"symbol":sym,"direction":s,"timestamp_ms":c[0],"timestamp_utc":datetime.fromtimestamp(c[0]/1000,timezone.utc).isoformat(),
   "two_hour_return_pct":round(final,6) if final is not None else None,"first10_directional_move_pct":round(early,6) if early is not None else None,
   "two_hour_first10_ratio":round(ratio,6) if ratio is not None else None,"strict_hold":strict,"tolerant_117_of_120_hold":tol,
   "gradual_strict":gradual,"gradual_tolerant":tg,"fast_spike":spike,
   "label":"GRADUAL_TREND" if gradual else "FAST_SPIKE" if spike else "FAILED_OR_WEAK",
   "first_hour_candle_counts":{"green":colors.count("GREEN"),"red":colors.count("RED"),"doji":colors.count("DOJI"),
    "directional":sum(x[4]>x[1] if s=="LONG" else x[4]<x[1] for x in hour)},
   "first_hour_candle_colors":colors,"pre_breakout_features":pf,"post_breakout_features":qf})
 return out
def stats(events,key):
 groups={k:[e for e in events if e["label"]==k] for k in ("GRADUAL_TREND","FAST_SPIKE","FAILED_OR_WEAK")};out={}
 for w in map(str,W):
  out[w]={}
  for f in ("directional_return_pct","directional_candle_share","path_efficiency","turnover_vs_pre60","taker_buy_sell_quote_ratio"):
   out[w][f]={k:{"n":len(v),"median":med([e[key][w].get(f) for e in v])} for k,v in groups.items()}
 return out,groups
async def main():
 OUT.mkdir(parents=True,exist_ok=True);end=int(time.time()*1000)//MIN*MIN;start=end-DAYS*1440*MIN
 timeout=aiohttp.ClientTimeout(total=60,connect=20);sem=asyncio.Semaphore(8)
 async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=16)) as ss:
  info,tickers=await asyncio.gather(get(ss,sem,"/fapi/v1/exchangeInfo"),get(ss,sem,"/fapi/v1/ticker/24hr"))
  valid={x["symbol"] for x in info["symbols"] if x.get("status")=="TRADING" and x.get("contractType")=="PERPETUAL" and x.get("quoteAsset")=="USDT"}
  uni=[x["symbol"] for x in sorted((x for x in tickers if x.get("symbol") in valid),key=lambda x:float(x.get("quoteVolume",0)),reverse=True)[:200]]
  data=await asyncio.gather(*(fetch(ss,sem,s,start,end) for s in uni))
 events=[];coverage=[]
 for sym,rs,errs in data:
  ev=scan(sym,rs);events.extend(ev);coverage.append({"symbol":sym,"candles":len(rs),"coverage_pct":round(100*len(rs)/20160,3),"events":len(ev),"errors":errs})
 events.sort(key=lambda e:(e["timestamp_ms"],e["symbol"]))
 pre,groups=stats(events,"pre_breakout_features");post,_=stats(events,"post_breakout_features")
 counts={k:len(v) for k,v in groups.items()};splits={}
 c1=start+(end-start)*9//14;c2=start+(end-start)*11//14
 for name,lo,hi in (("train_days_1_9",start,c1),("validation_days_10_11",c1,c2),("test_days_12_14",c2,end)):
  p=[e for e in events if lo<=e["timestamp_ms"]<hi]
  splits[name]={"events":len(p),"gradual":sum(e["label"]=="GRADUAL_TREND" for e in p),"spikes":sum(e["label"]=="FAST_SPIKE" for e in p),"failed":sum(e["label"]=="FAILED_OR_WEAK" for e in p)}
 summary={"exchange":"Binance USDⓈ-M Futures","api_access":"public unauthenticated market-data endpoints","api_key_required":False,
  "window_start_utc":datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),"window_end_utc":datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),
  "duration_days":14,"universe":"Top 200 currently trading USDT perpetuals by current 24h quote volume; not point-in-time historical universe.",
  "symbols_requested":len(uni),"symbols_95pct_coverage":sum(x["coverage_pct"]>=95 for x in coverage),"candles":sum(x["candles"] for x in coverage),
  "symbols_with_errors":sum(bool(x["errors"]) for x in coverage),"candidate_events":len(events),"labels":counts,
  "strict_gradual":sum(e["gradual_strict"] for e in events),"tolerant_gradual":sum(e["gradual_tolerant"] for e in events),
  "pre_breakout_medians":pre,"post_breakout_medians":post,"chronological_splits":splits,"coverage":coverage,"trading_enabled":False,
  "limitations":["Current top-200 universe creates survivorship/liquidity-selection bias.","Klines provide quote turnover and taker-buy quote volume as a pressure proxy.",
  "Historical OI/funding/long-short series are excluded from this first pass.","No fees, spread, slippage, funding or market-impact simulation.",
  "Associations do not prove causality; 14 days is exploratory."]}
 (OUT/"binance_14d_validation_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (OUT/"binance_14d_validation_events.jsonl").write_text("".join(json.dumps(e,separators=(",",":"))+"\n" for e in events))
 lines=["# Binance USD-M Futures: independent 14-day validation","",f"Window: {summary['window_start_utc']} to {summary['window_end_utc']}",
 "Access: public unauthenticated endpoints; no API key, account endpoint or order endpoint.",
 f"Markets: {len(uni)}; 1m candles: {summary['candles']}; >=95% coverage: {summary['symbols_95pct_coverage']}",
 f"Candidates: {len(events)}; labels: {json.dumps(counts)}",f"Strict gradual: {summary['strict_gradual']}; tolerant gradual: {summary['tolerant_gradual']}",
 "Event definition matches Bitget: close beyond prior 60m high/low; evaluate following 120m.",
 "Gradual: >=4% directional 2h return, at least 4x absolute first-10m move, and all 120 closes outside boundary; tolerant permits 3 retests.",
 "## Pre-breakout medians (candidate predictors)",json.dumps(pre,indent=2),
 "## Post-breakout medians (outcome diagnostics, not advance predictors)",json.dumps(post,indent=2),
 "## Chronological splits",json.dumps(splits,indent=2),"## Coverage",json.dumps(coverage,indent=2),"## Limitations"]
 lines.extend("- "+x for x in summary["limitations"]);lines.append("Raw event data is published as a workflow artifact.")
 (OUT/"binance_14d_validation_report.md").write_text("\n".join(lines)+"\n")
 print(json.dumps({"status":"complete","exchange":"Binance USD-M Futures","api_key_required":False,"markets":len(uni),
  "candles":summary["candles"],"events":len(events),"labels":counts,"strict_gradual":summary["strict_gradual"],
  "tolerant_gradual":summary["tolerant_gradual"],"symbols_95pct_coverage":summary["symbols_95pct_coverage"]},indent=2))
if __name__=="__main__":asyncio.run(main())
