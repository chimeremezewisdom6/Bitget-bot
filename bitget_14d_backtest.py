"""14-day Bitget USDT perpetual trend research. Read-only; no order endpoints.

Fresh reruns are triggered by the dedicated 14-day GitHub Actions workflow.
"""
import asyncio,base64,hashlib,hmac,json,math,os,statistics,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import aiohttp
BASE="https://api.bitget.com";CAT="USDT-FUTURES";M=60000;DAYS=14;H=120;PRE=60;CHUNK=950;HS=(1,3,5,10,15,30,60);OUT=Path(__file__).resolve().parent/"reports/daily_research"
def n(v,d=None):
 try:
  x=float(v);return x if math.isfinite(x) else d
 except (TypeError,ValueError):return d
def creds():
 def p(*ks):return next((os.getenv(k,"").strip() for k in ks if os.getenv(k,"").strip()),"")
 return p("BITGET_API_KEY","BITGET_KEY"),p("BITGET_API_SECRET","BITGET_SECRET_KEY","BITGET_SECRET"),p("BITGET_API_PASSPHRASE","BITGET_PASSPHRASE","BITGET_API_PASSWORD","BITGET_PASSWORD")
def signed(path,params):
 k,s,p=creds()
 if not all((k,s,p)):raise RuntimeError("Missing Bitget API credentials in GitHub Secrets.")
 q=urlencode(sorted(params.items()));ts=str(int(time.time()*1000))
 sig=base64.b64encode(hmac.new(s.encode(),(ts+"GET"+path+("?"+q if q else "")).encode(),hashlib.sha256).digest()).decode()
 return {"ACCESS-KEY":k,"ACCESS-SIGN":sig,"ACCESS-TIMESTAMP":ts,"ACCESS-PASSPHRASE":p},q
class Gate:
 def __init__(self):self.lock=asyncio.Lock();self.last=0
 async def wait(self):
  async with self.lock:
   d=1/14-(time.monotonic()-self.last)
   if d>0:await asyncio.sleep(d)
   self.last=time.monotonic()
async def get(ss,g,path,params=None,auth=False):
 params=params or {};headers=None;url=BASE+path
 if auth:
  headers,q=signed(path,params);url+=("?"+q if q else "");params=None
 err=None
 for i in range(6):
  await g.wait()
  try:
   async with ss.get(url,params=params,headers=headers) as r:
    if r.status==429 or r.status>=500:raise RuntimeError("HTTP "+str(r.status))
    r.raise_for_status();z=await r.json()
    if z.get("code")!="00000":raise RuntimeError(str(z.get("code"))+" "+str(z.get("msg")))
    return z.get("data",[])
  except Exception as e:
   err=e
   if i<5:await asyncio.sleep(min(20,1.5*2**i))
 raise RuntimeError(str(err))
def parse(raw):
 d={}
 for x in raw or []:
  try:
   if len(x)>=7:
    t=int(x[0]);d[t]={"ts":t,"o":n(x[1],0),"h":n(x[2],0),"l":n(x[3],0),"c":n(x[4],0),"q":n(x[6],0)}
  except Exception:pass
 return [d[k] for k in sorted(d)]
async def fetch(ss,g,sem,sym,start,end):
 async with sem:
  raw=[];errs=[];t=start
  while t<end:
   stop=min(end,t+CHUNK*M);p={"category":CAT,"symbol":sym,"interval":"1m","startTime":str(t),"endTime":str(stop-1),"limit":"1000","type":"market"}
   try:raw.extend(await get(ss,g,"/api/v3/market/candles",p) or [])
   except Exception as e:errs.append(str(e)[:150])
   t=stop
  return sym,[x for x in parse(raw) if start<=x["ts"]<end],errs
def pct(a,b):return (b/a-1)*100 if a else None
def dpct(a,b,s): 
 x=pct(a,b);return x if x is None or s=="LONG" else -x
def feat(w,s,base):
 if not w:return {}
 move=dpct(w[0]["o"],w[-1]["c"],s);path=sum(abs(pct(x["o"],x["c"]) or 0) for x in w)
 up=sum(x["c"]>x["o"] if s=="LONG" else x["c"]<x["o"] for x in w)
 return {"directional_return_pct":round(move,6) if move is not None else None,"directional_candle_share":round(up/len(w),6),
 "path_efficiency":round(abs(move)/path,6) if move is not None and path else None,
 "turnover_vs_pre60":round(statistics.mean(x["q"] for x in w)/base,6) if base else None}
def scan(sym,rs):
 out=[];last=-9999
 for i in range(PRE,len(rs)-H):
  if i-last<H:continue
  z=rs[i-PRE:i+H]
  if any(z[j]["ts"]-z[j-1]["ts"]!=M for j in range(1,len(z))):continue
  pre=rs[i-PRE:i];fut=rs[i:i+H];c=rs[i];hi=max(x["h"] for x in pre);lo=min(x["l"] for x in pre)
  if c["c"]>hi:s,b="LONG",hi
  elif c["c"]<lo:s,b="SHORT",lo
  else:continue
  last=i;final=dpct(c["o"],fut[-1]["c"],s);early=dpct(fut[0]["o"],fut[9]["c"],s)
  ratio=final/abs(early) if early is not None and abs(early)>1e-9 else None
  beyond=[x["c"]>b if s=="LONG" else x["c"]<b for x in fut];strict=all(beyond);tolerant=sum(beyond)>=117
  gradual=bool(strict and final is not None and final>=4 and ratio is not None and ratio>=4)
  tg=bool(tolerant and final is not None and final>=4 and ratio is not None and ratio>=4)
  spike=bool(final is not None and final>=4 and ratio is not None and ratio<4)
  base=statistics.mean(x["q"] for x in pre)
  pf={str(h):feat(pre[-h:],s,base) for h in HS};post={str(h):feat(fut[:h],s,base) for h in HS}
  if s=="LONG":mfe=max((x["h"]/c["o"]-1)*100 for x in fut);mae=min((x["l"]/c["o"]-1)*100 for x in fut)
  else:mfe=max((c["o"]/x["l"]-1)*100 if x["l"] else 0 for x in fut);mae=min((c["o"]/x["h"]-1)*100 if x["h"] else 0 for x in fut)
  label="GRADUAL_TREND" if gradual else ("FAST_SPIKE" if spike else "FAILED_OR_WEAK")
  first_hour=fut[:60]
  colors=["GREEN" if x["c"]>x["o"] else ("RED" if x["c"]<x["o"] else "DOJI") for x in first_hour]
  first_hour_counts={"green":colors.count("GREEN"),"red":colors.count("RED"),"doji":colors.count("DOJI"),"directional":sum(x["c"]>x["o"] if s=="LONG" else x["c"]<x["o"] for x in first_hour)}
  out.append({"symbol":sym,"direction":s,"timestamp_ms":c["ts"],"timestamp_utc":datetime.fromtimestamp(c["ts"]/1000,timezone.utc).isoformat(),
  "two_hour_return_pct":round(final,6) if final is not None else None,"first10_directional_move_pct":round(early,6) if early is not None else None,
  "two_hour_first10_ratio":round(ratio,6) if ratio is not None else None,"max_favorable_excursion_pct":round(mfe,6),"max_adverse_excursion_pct":round(mae,6),
  "strict_hold":strict,"tolerant_117_of_120_hold":tolerant,"gradual_strict":gradual,"gradual_tolerant":tg,"fast_spike":spike,"label":label,"first_hour_candle_counts":first_hour_counts,"first_hour_candle_colors":colors,
  "pre_breakout_features":pf,"post_breakout_features":post})
 return out
def med(a):
 a=[x for x in a if x is not None and math.isfinite(x)]
 return round(statistics.median(a),6) if a else None
def group_stats(es,key):
 groups={k:[e for e in es if e["label"]==k] for k in ("GRADUAL_TREND","FAST_SPIKE","FAILED_OR_WEAK")};out={}
 for h in map(str,HS):
  out[h]={}
  for f in ("directional_return_pct","directional_candle_share","path_efficiency","turnover_vs_pre60"):
   out[h][f]={k:{"n":len(v),"median":med([e[key][h].get(f) for e in v])} for k,v in groups.items()}
 return out,groups
async def main():
 OUT.mkdir(parents=True,exist_ok=True);end=int(time.time()*1000)//M*M;start=end-DAYS*1440*M
 g=Gate();timeout=aiohttp.ClientTimeout(total=50,connect=15)
 async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=24)) as ss:
  if not all(creds()):raise RuntimeError("Missing Bitget API credentials in GitHub Secrets; keys are never printed.")
  account=await get(ss,g,"/api/v3/account/info",auth=True);permission=account.get("permType","unknown") if isinstance(account,dict) else "unknown"
  try:fee=await get(ss,g,"/api/v3/account/all-fee-rate",{"category":CAT},True);fee_ok=bool(fee);fee_err=None
  except Exception as e:fee_ok=False;fee_err=str(e)[:150]
  ins,ticks=await asyncio.gather(get(ss,g,"/api/v3/market/instruments",{"category":CAT}),get(ss,g,"/api/v3/market/tickers",{"category":CAT}))
  live={x.get("symbol") for x in ins if x.get("status")=="online" and x.get("symbol") and (x.get("type")=="perpetual" or x.get("instrumentType")=="perpetual") and x.get("symbolType","crypto")=="crypto"}
  uni=sorted([x for x in ticks if x.get("symbol") in live],key=lambda x:n(x.get("turnover24h"),0),reverse=True)
  max_markets=int(os.getenv("BITGET_MAX_MARKETS","0"))
  if max_markets>0: uni=uni[:max_markets]
  sem=asyncio.Semaphore(10);data=await asyncio.gather(*(fetch(ss,g,sem,x["symbol"],start,end) for x in uni))
 events=[];coverage=[]
 for sym,rs,errs in data:
  ev=scan(sym,rs);events.extend(ev);coverage.append({"symbol":sym,"candles":len(rs),"coverage_pct":round(100*len(rs)/20160,3),"events":len(ev),"errors":errs})
 events.sort(key=lambda x:(x["timestamp_ms"],x["symbol"]))
 pre,groups=group_stats(events,"pre_breakout_features");post,_=group_stats(events,"post_breakout_features")
 counts={k:len(v) for k,v in groups.items()};daily=defaultdict(Counter)
 for e in events:daily[e["timestamp_utc"][:10]][e["label"]]+=1
 a=start+(end-start)*9//14;b=start+(end-start)*11//14;splits={}
 for name,lo,hi in (("train_days_1_9",start,a),("validation_days_10_11",a,b),("test_days_12_14",b,end)):
  es=[e for e in events if lo<=e["timestamp_ms"]<hi]
  splits[name]={"events":len(es),"gradual":sum(x["label"]=="GRADUAL_TREND" for x in es),"spikes":sum(x["label"]=="FAST_SPIKE" for x in es),"failed":sum(x["label"]=="FAILED_OR_WEAK" for x in es)}
 summary={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"window_start_utc":datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),"window_end_utc":datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),
 "duration_days":14,"authenticated_read":True,"permission_type":permission,"fee_schedule_available":fee_ok,"fee_schedule_error":fee_err,
 "universe":"Top 200 currently online USDT perpetuals by current turnover; not historical point-in-time universe.","symbols_requested":len(uni),
 "symbols_95pct_coverage":sum(x["coverage_pct"]>=95 for x in coverage),"candles":sum(x["candles"] for x in coverage),"symbols_with_errors":sum(bool(x["errors"]) for x in coverage),
 "candidate_events":len(events),"labels":counts,"strict_gradual":sum(x["gradual_strict"] for x in events),"tolerant_gradual":sum(x["gradual_tolerant"] for x in events),
 "pre_breakout_medians":pre,"post_breakout_medians":post,"chronological_splits":splits,"daily_counts":{k:dict(v) for k,v in sorted(daily.items())},"coverage":coverage,
 "limitations":["Current live universe creates survivorship bias; historical listings/delisted contracts are not reconstructed.","Observational associations do not prove causality.",
 "Pre-breakout features are separate from post-breakout features.","No historical taker-side flow, funding history or historical order-book depth is claimed.",
 "Aggregate OI is not used to infer which side opened positions.","Fee schedule alone is not a complete execution-cost model; spread, slippage and funding need historical data.",
 "Strict label requires all 120 closes beyond boundary; tolerant label permits three retests.","14 days is exploratory; extend out-of-sample before treating any pattern as predictive."],"trading_enabled":False}
 (OUT/"bitget_14d_trend_fuel_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (OUT/"bitget_14d_trend_fuel_events.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in events))
 qualifying=[e for e in events if e["gradual_tolerant"]]
 (OUT/"bitget_14d_gradual_event_details.jsonl").write_text("".join(json.dumps(e,separators=(",",":"))+"\n" for e in qualifying))
 lines=["# Bitget 14-day trend fuel backtest","",f"Window: {summary['window_start_utc']} to {summary['window_end_utc']}",f"Authenticated read: SUCCESS; permission: {permission}; fee schedule: {fee_ok}",
 f"Markets: {len(uni)}; candles: {summary['candles']}; symbols with >=95% coverage: {summary['symbols_95pct_coverage']}",
 f"Candidates: {len(events)}; groups: {json.dumps(counts)}",f"Strict gradual: {summary['strict_gradual']}; tolerant gradual: {summary['tolerant_gradual']}","",
 "Candidate: closed 1m close beyond previous 60m high/low. Outcomes measured over following 120m.",
 "Gradual: >=4% direction-adjusted return, full 2h move at least 4x absolute first-10m move, and all 120 closes beyond breakout boundary.",
 "Tolerant label permits three closes back through boundary. Pre-breakout features use candles before the breakout candle.",
 "## Pre-breakout feature medians","JSON follows:",json.dumps(pre,indent=2),"## Post-breakout features (not advance predictors)",json.dumps(post,indent=2),
 "## Chronological splits",json.dumps(splits,indent=2),"## Daily event counts",json.dumps({k:dict(v) for k,v in sorted(daily.items())},indent=2),
 "## Coverage",json.dumps(coverage,indent=2),"## Limitations"]
 lines.extend("- "+x for x in summary["limitations"]);lines.extend(["Raw event rows: bitget_14d_trend_fuel_events.jsonl","Gradual event details with first-hour candle colours: bitget_14d_gradual_event_details.jsonl"])
 (OUT/"bitget_14d_trend_fuel_report.md").write_text("\n".join(lines)+"\n")
 print(json.dumps({"status":"complete","authenticated":True,"permission":permission,"markets":len(uni),"candles":summary["candles"],"events":len(events),"groups":counts,"strict_gradual":summary["strict_gradual"],"tolerant_gradual":summary["tolerant_gradual"]},indent=2))
if __name__=="__main__":asyncio.run(main())
