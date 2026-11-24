"""Bitget public-trade aggressor-decay reversal backtest; read-only."""
import asyncio,aiohttp,json,math,statistics,time
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
BASE="https://api.bitget.com"; ROOT=Path(__file__).resolve().parent
OUT=ROOT/"reports/aggressor_decay"
START=int(datetime(2026,11,10,tzinfo=timezone.utc).timestamp()*1000)
END=int(datetime(2026,11,24,tzinfo=timezone.utc).timestamp()*1000)
TOP_N=10; GAP=.13; H=(1,3,5,10,20,30)
class Gate:
 def __init__(self): self.lock=asyncio.Lock(); self.last=0
 async def wait(self):
  async with self.lock:
   d=GAP-(time.monotonic()-self.last)
   if d>0: await asyncio.sleep(d)
   self.last=time.monotonic()
def n(x,d=0):
 try:
  v=float(x); return v if math.isfinite(v) else d
 except: return d
async def get(s,path,p,g):
 err=None
 for k in range(6):
  await g.wait()
  try:
   async with s.get(BASE+path,params=p) as r:
    if r.status==429 or r.status>=500: raise RuntimeError("HTTP "+str(r.status))
    r.raise_for_status(); x=await r.json()
    if x.get("code")!="00000": raise RuntimeError(str(x.get("code"))+" "+str(x.get("msg")))
    return x.get("data")
  except Exception as e:
   err=e
   if k<5: await asyncio.sleep(min(20,2**k))
 raise RuntimeError(str(err))
async def universe(s,g):
 c=await get(s,"/api/v2/mix/market/contracts",{"productType":"USDT-FUTURES"},g)
 t=await get(s,"/api/v2/mix/market/tickers",{"productType":"USDT-FUTURES"},g)
 cm={x["symbol"]:x for x in c if x.get("symbol") and x.get("symbolStatus")=="normal" and x.get("symbolType","perpetual")=="perpetual"}
 t=sorted([x for x in t if x.get("symbol") in cm],key=lambda x:n(x.get("usdtVolume",x.get("quoteVolume"))),reverse=True)[:TOP_N]
 return [(x["symbol"],n(cm[x["symbol"]].get("takerFeeRate"),.0006),n(x.get("usdtVolume",x.get("quoteVolume")))) for x in t]
async def fetch_window(s,sym,lo,hi,g):
 out=[]; cursor=None; seen=set(); pages=0
 while pages<20000:
  p={"symbol":sym,"productType":"USDT-FUTURES","startTime":str(lo),"endTime":str(hi),"limit":"1000"}
  if cursor: p["idLessThan"]=cursor
  rows=await get(s,"/api/v2/mix/market/fills-history",p,g); pages+=1
  if not rows: break
  ids=[]; oldest=hi
  for x in rows:
   ts=int(n(x.get("ts"))); tid=str(x.get("tradeId",""))
   if lo<=ts<hi and tid not in seen:
    if tid: seen.add(tid); ids.append(tid)
    side=str(x.get("side","")).lower(); px=n(x.get("price")); sz=n(x.get("size"))
    if side in ("buy","sell") and px>0 and sz>0: out.append((ts,side,px*sz,px))
   oldest=min(oldest,ts)
  if len(rows)<1000 or not ids or oldest<=lo: break
  nxt=min(ids,key=lambda z:int(z))
  if nxt==cursor: break
  cursor=nxt
 return out,pages
def bucket(rows):
 b={}
 for ts,side,q,px in rows:
  t=ts//60000*60000
  x=b.setdefault(t,{"buy":0.,"sell":0.,"hi":0.,"lo":float("inf"),"cts":-1,"close":0.})
  x[side]+=q; x["hi"]=max(x["hi"],px); x["lo"]=min(x["lo"],px)
  if ts>=x["cts"]: x["cts"],x["close"]=ts,px
 return b
def pct(a,p):
 a=sorted(a)
 return a[min(len(a)-1,int((len(a)-1)*p))] if a else 0.
def run_symbol(sym,b,fee):
 ts=sorted(b); ev=[]
 if len(ts)<400: return ev
 last={"buy":-10**18,"sell":-10**18}
 for i in range(360,len(ts)-31):
  t=ts[i]
  if any(ts[j]-ts[j-1]!=60000 for j in range(i-39,i+31)): continue
  w=[b[t-k*60000] for k in range(9,-1,-1)]
  hist=[b[t-k*60000] for k in range(10,370)]
  for side in ("buy","sell"):
   v=[x[side] for x in w]; a=statistics.mean(v[:3]); z=statistics.mean(v[-3:])
   base=[x[side] for x in hist if x[side]>0]; q25=pct(base,.25)
   slope=sum((j-4.5)*(x-statistics.mean(v)) for j,x in enumerate(v))
   if not (len(base)>=100 and a>0 and z<=a*.5 and slope<0 and q25>0 and z<=q25): continue
   if t-last[side]<600000: continue
   last[side]=t; direction="SHORT" if side=="buy" else "LONG"; entry=b[t]["close"]
   if entry<=0: continue
   row={"symbol":sym,"time":datetime.fromtimestamp(t/1000,timezone.utc).isoformat(),"decaying_side":side.upper(),"direction":direction,"first3m_mean_quote":a,"last3m_mean_quote":z,"decay_ratio":z/a,"entry":entry,"fee_roundtrip_bps":fee*20000,"outcomes":{}}
   for h in H:
    f=[b[t+k*60000] for k in range(1,h+1)]; ex=f[-1]["close"]
    gross=((entry/ex)-1)*100 if direction=="SHORT" else ((ex/entry)-1)*100
    mfe=((entry/min(x["lo"] for x in f))-1)*100 if direction=="SHORT" else (max(x["hi"] for x in f)/entry-1)*100
    mae=((entry/max(x["hi"] for x in f))-1)*100 if direction=="SHORT" else (min(x["lo"] for x in f)/entry-1)*100
    net=gross-fee*200
    row["outcomes"][str(h)]={"gross_pct":gross,"net_pct":net,"mfe_pct":mfe,"mae_pct":mae,"win":net>0}
   ev.append(row)
 return ev
def stats(es):
 out={}
 for h in H:
  a=[x["outcomes"][str(h)] for x in es]; r=[x["net_pct"] for x in a]
  out[str(h)]={"trades":len(r),"net_win_rate_pct":round(sum(x>0 for x in r)*100/len(r),2) if r else None,"mean_net_pct":round(statistics.mean(r),5) if r else None,"median_net_pct":round(statistics.median(r),5) if r else None,"mean_mfe_pct":round(statistics.mean(x["mfe_pct"] for x in a),5) if r else None,"mean_mae_pct":round(statistics.mean(x["mae_pct"] for x in a),5) if r else None}
 return out
async def main():
 OUT.mkdir(parents=True,exist_ok=True); gate=Gate()
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90,connect=20),connector=aiohttp.TCPConnector(limit=30)) as s:
  uni=await universe(s,gate); sem=asyncio.Semaphore(4)
  async def one(x):
   async with sem:
    sym,fee,turn=x; allr=[]; pages=0; mid=START+7*86400000
    for lo,hi in ((START,mid),(mid,END)):
     rr,pp=await fetch_window(s,sym,lo,hi,gate); allr+=rr; pages+=pp
    b=bucket(allr); es=run_symbol(sym,b,fee)
    return {"symbol":sym,"turnover_24h_usdt":turn,"fee_rate":fee,"raw_trades":len(allr),"pages":pages,"minutes":len(b),"signals":len(es)},es
  results=await asyncio.gather(*(one(x) for x in uni),return_exceptions=True)
 coverage=[]; events=[]; failures=[]
 for x in results:
  if isinstance(x,Exception): failures.append(str(x)[:250])
  else: coverage.append(x[0]); events+=x[1]
 allstats=stats(events); dirs={d:stats([e for e in events if e["direction"]==d]) for d in ("LONG","SHORT")}
 payload={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"start_utc":datetime.fromtimestamp(START/1000,timezone.utc).isoformat(),"end_utc":datetime.fromtimestamp(END/1000,timezone.utc).isoformat(),"universe":"top 10 current turnover USDT perpetuals","coverage":coverage,"failures":failures,"signals":len(events),"definition":"last 3m mean aggressive-side quote notional <=50% of first 3m mean in a 10m window; negative linear slope; final 3m <= prior 6h 25th percentile; take opposite side; same-side signal throttle 10m","results":allstats,"by_direction":dirs,"events":events,"limitations":["Trade side is used as aggressor-side proxy; validate side semantics.","Current top-turnover universe creates survivorship bias.","Last-trade entry/exit omits spread and slippage.","Contract taker fee metadata used; no account-specific tier adjustment.","Signals require continuous minute buckets and full 30m forward data."]}
 (OUT/"aggressor_decay_events.json").write_text(json.dumps(payload,indent=2)+"\\n")
 lines=["# Bitget aggressor-decay reversal backtest","",f"Window: {payload['start_utc']} to {payload['end_utc']}",f"Universe: {len(coverage)} top-current-turnover USDT perpetuals; events: {len(events)}",f"Fetch failures: {len(failures)}","","Signal: "+payload["definition"],"","## Combined outcomes (estimated round-trip taker fees deducted; spread/slippage excluded)","| Horizon | Trades | Net win % | Mean net % | Median net % | Mean MFE % | Mean MAE % |","|---:|---:|---:|---:|---:|---:|---:|"]
 for h,x in allstats.items(): lines.append(f"| {h}m | {x['trades']} | {x['net_win_rate_pct']} | {x['mean_net_pct']} | {x['median_net_pct']} | {x['mean_mfe_pct']} | {x['mean_mae_pct']} |")
 for d,xs in dirs.items():
  lines+=["",f"## {d}"]
  for h,x in xs.items(): lines.append(f"- {h}m: n={x['trades']}, win={x['net_win_rate_pct']}%, mean net={x['mean_net_pct']}%, median={x['median_net_pct']}%")
 lines+=["","## Coverage","| Symbol | Trades | Minutes | Signals | Pages |","|---|---:|---:|---:|---:|"]
 for x in coverage: lines.append(f"| {x['symbol']} | {x['raw_trades']} | {x['minutes']} | {x['signals']} | {x['pages']} |")
 lines+=["","## Limitations"]+["- "+x for x in payload["limitations"]]
 (OUT/"aggressor_decay_report.md").write_text("\\n".join(lines)+"\\n")
 print(json.dumps({"status":"complete","coverage":coverage,"failures":failures,"signals":len(events),"results":allstats,"by_direction":dirs},indent=2))
if __name__=="__main__": asyncio.run(main())
