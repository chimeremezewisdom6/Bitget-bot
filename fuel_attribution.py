"""Bitget fuel attribution: gradual trends vs failed breakouts and fast spikes.
Observational study only; no market feature is claimed to cause price movement.
"""
import asyncio,base64,hashlib,hmac,json,math,os,statistics,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import aiohttp
OUT=Path(__file__).resolve().parent/"reports/daily_research"
BASE="https://api.bitget.com";CAT="USDT-FUTURES";N=200;H=120;HS=(1,3,5,10,15,30)
def n(x,d=None):
 try:
  z=float(x);return z if math.isfinite(z) else d
 except (TypeError,ValueError):return d
def credentials():
 def p(*ks):return next((os.getenv(k,"").strip() for k in ks if os.getenv(k,"").strip()),"")
 return p("BITGET_API_KEY","BITGET_KEY"),p("BITGET_API_SECRET","BITGET_SECRET_KEY","BITGET_SECRET"),p("BITGET_API_PASSPHRASE","BITGET_PASSPHRASE","BITGET_API_PASSWORD","BITGET_PASSWORD")
def sign(path,params=None):
 k,s,p=credentials()
 if not all((k,s,p)):raise RuntimeError("Bitget API credentials missing")
 q=urlencode(sorted((params or {}).items()));ts=str(int(time.time()*1000))
 sig=base64.b64encode(hmac.new(s.encode(),(ts+"GET"+path+(("?"+q) if q else "")).encode(),hashlib.sha256).digest()).decode()
 return {"ACCESS-KEY":k,"ACCESS-SIGN":sig,"ACCESS-TIMESTAMP":ts,"ACCESS-PASSPHRASE":p},q
async def get(ss,path,params=None,auth=False):
 if auth:
  h,q=sign(path,params);url=BASE+path+(("?"+q) if q else "");params=None
 else:h=None;url=BASE+path
 err=None
 for i in range(4):
  try:
   async with ss.get(url,params=params,headers=h,timeout=25) as r:
    if r.status==429 or r.status>=500:raise RuntimeError("HTTP "+str(r.status))
    r.raise_for_status();p=await r.json()
    if p.get("code")!="00000":raise RuntimeError(str(p.get("code"))+" "+str(p.get("msg")))
    return p.get("data",[])
  except Exception as e:
   err=e
   if i<3:await asyncio.sleep(1+i)
 raise RuntimeError(str(err))
def norm(raw):
 d={}
 for x in raw or []:
  try:
   if len(x)>=7:
    t=int(x[0]);d[t]={"ts":t,"o":n(x[1],0),"h":n(x[2],0),"l":n(x[3],0),"c":n(x[4],0),"q":n(x[6],0)}
  except Exception:pass
 return [d[k] for k in sorted(d)]
def ret(a,b,side):
 return ((b/a)-1)*100*(1 if side=="LONG" else -1) if a and b else None
def detect(sym,rs):
 out=[];last=-9999
 for i in range(60,len(rs)-H):
  if i-last<120:continue
  pre=rs[i-60:i];fut=rs[i:i+H]
  if len(fut)!=H or any(rs[j]["ts"]-rs[j-1]["ts"]!=60000 for j in range(i-60,i+H)):continue
  hi=max(x["h"] for x in pre);lo=min(x["l"] for x in pre);first=rs[i]
  if first["c"]>hi:side="LONG";boundary=hi
  elif first["c"]<lo:side="SHORT";boundary=lo
  else:continue
  last=i;final=ret(first["c"],fut[-1]["c"],side);early=ret(fut[0]["o"],fut[9]["c"],side)
  ratio=final/abs(early) if final is not None and early is not None and abs(early)>1e-9 else None
  held=all(x["c"]>boundary for x in fut) if side=="LONG" else all(x["c"]<boundary for x in fut)
  gradual=bool(held and final is not None and final>=4 and ratio is not None and ratio>=4)
  spike=bool(final is not None and final>=4 and ratio is not None and ratio<4)
  base=statistics.mean(x["q"] for x in pre[-20:]);features={}
  for m in HS:
   w=fut[:m];move=ret(first["o"],w[-1]["c"],side)
   aligned=sum(1 for x in w if (x["c"]>x["o"] if side=="LONG" else x["c"]<x["o"]))
   vol=statistics.mean(x["q"] for x in w);path=sum(abs(ret(x["o"],x["c"],side) or 0) for x in w)
   features[str(m)]={"directional_return_pct":round(move,5) if move is not None else None,"directional_candle_share":round(aligned/m,5),"turnover_vs_pre20":round(vol/base,5) if base else None,"path_efficiency":round(abs(move)/path,5) if move is not None and path else None}
  out.append({"symbol":sym,"direction":side,"start_timestamp_ms":first["ts"],"start_utc":datetime.fromtimestamp(first["ts"]/1000,timezone.utc).isoformat(),"two_hour_return_pct":round(final,5) if final is not None else None,"first10_move_pct":round(early,5) if early is not None else None,"two_hour_first10_ratio":round(ratio,5) if ratio is not None else None,"held_120m":held,"gradual_trend":gradual,"fast_spike":spike,"features":features,"oi_change_2h_pct":None})
 return out
def med(a):
 a=[x for x in a if x is not None and math.isfinite(x)]
 return round(statistics.median(a),5) if a else None
def compare(events):
 groups={"GRADUAL_TREND":[e for e in events if e["gradual_trend"]],"FAST_SPIKE":[e for e in events if e["fast_spike"]],"FAILED_OR_WEAK":[e for e in events if not e["gradual_trend"] and not e["fast_spike"]]}
 by={}
 for h in map(str,HS):
  by[h]={}
  for feat in ("turnover_vs_pre20","directional_candle_share","path_efficiency","directional_return_pct"):
   by[h][feat]={k:{"n":len(v),"median":med([e["features"][h][feat] for e in v])} for k,v in groups.items()}
 ranking=[]
 for feat in ("turnover_vs_pre20","directional_candle_share","path_efficiency"):
  g=med([e["features"]["10"][feat] for e in groups["GRADUAL_TREND"]])
  c=med([e["features"]["10"][feat] for k in ("FAST_SPIKE","FAILED_OR_WEAK") for e in groups[k]])
  if g is not None and c is not None:ranking.append({"feature":feat,"gradual_median":g,"control_median":c,"median_ratio":round(g/c,4) if c else None})
 return {"group_counts":{k:len(v) for k,v in groups.items()},"by_horizon":by,"10m_feature_comparison":ranking}
async def main():
 OUT.mkdir(parents=True,exist_ok=True);end=int(time.time()*1000)//60000*60000;start=end-1440*60000;mid=start+720*60000
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45,connect=12)) as ss:
  info=await get(ss,"/api/v3/account/info",auth=True);perm=info.get("permType","unknown") if isinstance(info,dict) else "unknown"
  try:fees=await get(ss,"/api/v3/account/all-fee-rate",{"category":CAT},True);fee_ok=bool(fees)
  except Exception:fee_ok=False
  ins,ticks=await asyncio.gather(get(ss,"/api/v3/market/instruments",{"category":CAT}),get(ss,"/api/v3/market/tickers",{"category":CAT}))
  online={x.get("symbol") for x in ins if x.get("status")=="online" and (x.get("type")=="perpetual" or x.get("instrumentType")=="perpetual") and x.get("symbolType","crypto")=="crypto"}
  uni=sorted([x for x in ticks if x.get("symbol") in online],key=lambda x:n(x.get("turnover24h"),0),reverse=True)[:N]
  sem=asyncio.Semaphore(8)
  async def fetch(t):
   async with sem:
    async def page(a,b):return await get(ss,"/api/v3/market/candles",{"category":CAT,"symbol":t["symbol"],"interval":"1m","startTime":str(a),"endTime":str(b),"limit":"1000"})
    try:
     a,b=await asyncio.gather(page(start,mid),page(mid,end));rr=norm(a+b)
     if len(rr)<1300:raise RuntimeError("incomplete candles "+str(len(rr)))
     return t["symbol"],rr,None
    except Exception as e:return t["symbol"],[],str(e)[:160]
  fetched=await asyncio.gather(*(fetch(t) for t in uni));events=[];coverage=[]
  for sym,rr,err in fetched:
   ev=detect(sym,rr) if rr else [];events.extend(ev);coverage.append({"symbol":sym,"candles":len(rr),"candidates":len(ev),"error":err})
  symbols=sorted({e["symbol"] for e in events});oi_cov=[]
  async def enrich(sym):
   try:
    p=await get(ss,"/api/v3/market/open-interest-history",{"symbol":sym,"period":"5m"})
    raw=p.get("list",[]) if isinstance(p,dict) else p;pts=[]
    for x in raw or []:
     ts=int(n(x.get("timestamp",x.get("ts")),0) or 0);v=n(x.get("openInterestValue",x.get("openInterest")))
     if ts and v and v>0:pts.append((ts,v))
    count=0
    for e in events:
     if e["symbol"]!=sym or len(pts)<2:continue
     a=min(pts,key=lambda z:abs(z[0]-e["start_timestamp_ms"]));b=min(pts,key=lambda z:abs(z[0]-(e["start_timestamp_ms"]+H*60000)))
     if abs(a[0]-e["start_timestamp_ms"])<=600000 and abs(b[0]-(e["start_timestamp_ms"]+H*60000))<=600000 and b[0]>a[0]:
      e["oi_change_2h_pct"]=round((b[1]/a[1]-1)*100,5);count+=1
    return {"symbol":sym,"oi_points":len(pts),"events_with_aligned_oi":count}
   except Exception as e:return {"symbol":sym,"error":str(e)[:140]}
  oi_cov=await asyncio.gather(*(enrich(x) for x in symbols))
 comp=compare(events);grad=comp["group_counts"]["GRADUAL_TREND"];spike=comp["group_counts"]["FAST_SPIKE"]
 report=["# Bitget fuel attribution — event/control research","",
 "Generated UTC: "+datetime.now(timezone.utc).isoformat(),
 "Window UTC: "+datetime.fromtimestamp(start/1000,timezone.utc).isoformat()+" to "+datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),
 "Authenticated Bitget read: SUCCESS; permission: "+str(perm)+"; fee schedule: "+str(fee_ok),
 "Universe: "+str(len(uni))+" top online crypto USDT perpetuals; symbols with >=1300 candles: "+str(sum(x["candles"]>=1300 for x in coverage))+"/"+str(len(uni))+"; candles: "+str(sum(x["candles"] for x in coverage))+"; fetch errors: "+str(sum(bool(x["error"]) for x in coverage)),
 "Breakout candidates: "+str(len(events))+"; gradual trends: "+str(grad)+"; fast 4% spikes: "+str(spike),"",
 "## Labels and controls",
 "Candidate: closed 1m close beyond prior 60m high/low; measure next 120m without pre-selecting successful holds.",
 "Gradual: holds breakout level for 120m, returns >=4%, and 2h move >=4x absolute first-10m move.",
 "Fast spike: reaches >=4% but fails 4x rule. Failed/weak: all other breakout candidates.",
 "Early features at 1/3/5/10/15/30m use only candles available by that horizon. Turnover vs previous 20m baseline.",
 "## 10-minute feature comparison","| Feature | Gradual median | Controls median | Ratio |","|---|---:|---:|---:|"]
 for x in comp["10m_feature_comparison"]:report.append("| "+x["feature"]+" | "+str(x["gradual_median"])+" | "+str(x["control_median"])+" | "+str(x["median_ratio"])+" |")
 report+=["","## Group counts",json.dumps(comp["group_counts"],indent=2),"","## Feature medians at all horizons",json.dumps(comp["by_horizon"],indent=2,sort_keys=True),"",
 "## Historical open interest","Timestamp-aligned OI events: "+str(sum(x.get("events_with_aligned_oi",0) for x in oi_cov))+"/"+str(len(events))+" across "+str(len(oi_cov))+" symbols.",
 "Aggregate OI does not identify whether longs or shorts opened. Missing timestamp-aligned history is null.",
 "## Causality assessment",
 "This is an observational event/control comparison, not a randomized intervention. It cannot prove a feature caused a trend.",
 "A feature is more credible when it appears before later expansion and separates gradual trends from both failed-breakout and fast-spike controls.",
 "No historical taker-side flow, funding or order-book values are invented. Current snapshots are not used as historical evidence.",
 "One 24h sample is exploratory; confirm rankings with a multi-week time-separated test and transaction-cost assumptions.",
 "Full event rows: bitget_fuel_attribution_events.jsonl."]
 (OUT/"bitget_fuel_attribution_report.md").write_text("\\n".join(report),encoding="utf-8")
 (OUT/"bitget_fuel_attribution_events.jsonl").write_text("".join(json.dumps(e,separators=(",",":"))+"\\n" for e in events),encoding="utf-8")
 summary={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"window_start_ms":start,"window_end_ms":end,"authenticated":True,"permission_type":perm,"fee_schedule_available":fee_ok,"symbols_requested":len(uni),"symbols_with_usable_candles":sum(x["candles"]>=1300 for x in coverage),"candles":sum(x["candles"] for x in coverage),"fetch_errors":[x for x in coverage if x["error"]],"candidate_events":len(events),"gradual_trends":grad,"fast_spikes":spike,"comparison":comp,"oi_coverage":oi_cov,"causality":"observational only"}
 (OUT/"bitget_fuel_attribution_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
 print(json.dumps({"symbols":len(uni),"events":len(events),"gradual":grad,"fast_spikes":spike,"oi_aligned_events":sum(x.get("events_with_aligned_oi",0) for x in oi_cov)},indent=2))
if __name__=="__main__":asyncio.run(main())
