"""24h read-only Bitget USDT futures research collector."""
import argparse,asyncio,json,math,time,hashlib
from datetime import datetime,timezone
from pathlib import Path
import aiohttp,xml.etree.ElementTree as ET
R=Path("reports/daily_research"); S=R/"session.json"; O=R/"market_observations.jsonl"; P=R/"public_trader_posts.jsonl"; E=R/"shadow_experiments.jsonl"; Q=R/"pending.json"; SUMMARY=R/"daily_research_summary.md"
FEEDS=["https://www.reddit.com/r/BitcoinMarkets/new/.rss","https://www.reddit.com/r/Daytrading/new/.rss","https://www.reddit.com/r/CryptoCurrency/new/.rss","https://www.coindesk.com/arc/outboundfeeds/rss/","https://cointelegraph.com/rss"]
H={"User-Agent":"Bitget-ReadOnly-Research/1.0"}
def now(): return datetime.now(timezone.utc)
def iso(): return now().isoformat()
def n(x,d=0):
 try:
  y=float(x); return y if math.isfinite(y) else d
 except: return d
def read(p,d):
 try:return json.loads(p.read_text())
 except:return d
def add(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("a",encoding="utf8") as f:f.write(json.dumps(x,ensure_ascii=False)+"\n")
async def get(s,path,params=None,url=False):
 async with s.get(path if url else "https://api.bitget.com"+path,params=params,timeout=18) as r:
  r.raise_for_status(); x=await r.json()
  if x.get("code") not in (None,"00000"):raise RuntimeError(str(x))
  return x
def ema(a,k):
 if len(a)<k:return None
 v=sum(a[:k])/k; alpha=2/(k+1)
 for z in a[k:]:v=z*alpha+v*(1-alpha)
 return v
def rsi(a):
 if len(a)<15:return None
 d=[a[i]-a[i-1] for i in range(1,len(a))][-14:]
 g=sum(max(x,0) for x in d)/14;l=sum(max(-x,0) for x in d)/14
 return 100 if l==0 else 100-100/(1+g/l)
async def posts(s):
 known=set()
 if P.exists():
  for line in P.read_text().splitlines():
   try:known.add(json.loads(line)["id"])
   except:pass
 count=0
 for feed in FEEDS:
  try:
   async with s.get(feed,headers=H,timeout=15) as r:r.raise_for_status();raw=await r.text()
   root=ET.fromstring(raw); entries=root.findall(".//item")+root.findall(".//{http://www.w3.org/2005/Atom}entry")
   for e in entries[:25]:
    def val(k):
     z=e.find(k) or e.find("{http://www.w3.org/2005/Atom}"+k)
     return (z.get("href") if k=="link" and z is not None and z.get("href") else (z.text or "").strip() if z is not None else "")
    title=val("title");link=val("link");key=hashlib.sha256((link or title).encode()).hexdigest()
    if not title or key in known:continue
    add(P,{"id":key,"source":feed,"title":title[:500],"url":link,"published":val("pubDate") or val("published"),"summary":(val("description") or val("summary"))[:2500],"collected_at_utc":iso(),"classification":"UNVERIFIED_PUBLIC_CLAIM_OR_COMMENTARY","verification":"No proof of identity, actual fills or profitable track record."});known.add(key);count+=1
  except Exception as ex:add(R/"collection_errors.jsonl",{"at":iso(),"feed":feed,"error":str(ex)[:300]})
 return count
def strategy(candles,price,spread,fee):
 rows=sorted(candles,key=lambda x:int(x[0]));cut=int(time.time()*1000)-60000;rows=[x for x in rows if int(x[0])<cut]
 c=[n(x[4]) for x in rows if n(x[4])>0]
 if len(c)<30:return []
 e9,e21=ema(c,9),ema(c,21);rv=rsi(c);avg=sum(n(x[6]) for x in rows[-21:-1])/20;vol=n(rows[-1][6]);out=[]
 common={"symbol":"","observed_at_utc":iso(),"reference_price":price,"estimated_round_trip_cost_bps":spread+2*fee*10000,"evidence":"hypothesis only"}
 if e9 and e21 and e9>e21 and c[-1]>e9 and vol>avg*1.2:out.append(("ema_volume","LONG","EMA9>EMA21, close>EMA9, turnover>1.2x mean"))
 if e9 and e21 and e9<e21 and c[-1]<e9 and vol>avg*1.2:out.append(("ema_volume","SHORT","EMA9<EMA21, close<EMA9, turnover>1.2x mean"))
 hi=max(n(x[2]) for x in rows[-21:-1]);lo=min(n(x[3]) for x in rows[-21:-1])
 if c[-1]>hi and vol>avg*1.5:out.append(("breakout","LONG","20-bar high break with >1.5x turnover"))
 if c[-1]<lo and vol>avg*1.5:out.append(("breakdown","SHORT","20-bar low break with >1.5x turnover"))
 if rv is not None and rv<25:out.append(("oversold_watch","LONG",f"RSI14 {rv:.1f}; not reversal confirmation"))
 if rv is not None and rv>75:out.append(("overbought_watch","SHORT",f"RSI14 {rv:.1f}; not reversal confirmation"))
 return [(a,b,d) for a,b,d in out]
async def collect():
 st=read(S,{})
 if not st.get("active"):print("No active session");return
 if now().timestamp()>=st["end_epoch"]:
  st["active"]=False;st["ended_at_utc"]=iso();S.write_text(json.dumps(st,indent=2))
  SUMMARY.write_text("# 24-Hour Bitget Futures Research\n\n"+json.dumps(st,indent=2)+"\n\n## Evidence cautions\nPosts are unverified public claims. Signals are hypotheses. Forward outcomes are reference prices, not fills. Market cap is not provided by Bitget and remains unverified. Five-minute scheduled runs may be delayed or skipped. This exploratory day cannot prove profitability.\n\nFiles: market_observations.jsonl, public_trader_posts.jsonl, shadow_experiments.jsonl, collection_errors.jsonl.\n")
  print("Session ended");return
 R.mkdir(parents=True,exist_ok=True);errors=[];current={};signals=0
 async with aiohttp.ClientSession(headers=H) as s:
  try:
   inst,ticks=await asyncio.gather(get(s,"/api/v3/market/instruments",{"category":"USDT-FUTURES"}),get(s,"/api/v3/market/tickers",{"category":"USDT-FUTURES"}))
   meta={x["symbol"]:x for x in inst["data"] if x.get("status")=="online" and x.get("type")=="perpetual"}
   ranked=sorted([(n(t.get("turnover24h")),t,meta[t["symbol"]]) for t in ticks["data"] if t.get("symbol") in meta and n(t.get("turnover24h"))>=500000],reverse=True)[:15]
   for turnover,t,m in ranked:
    sym=t["symbol"];bid=n(t.get("bid1Price"));ask=n(t.get("ask1Price"));mid=(bid+ask)/2 if bid and ask else n(t.get("lastPrice"));current[sym]=n(t.get("lastPrice")) or mid
    spread=(ask-bid)/mid*10000 if mid and ask>=bid else 0
    ob=await get(s,"/api/v3/market/orderbook",{"category":"USDT-FUTURES","symbol":sym,"limit":"1000"})
    candles=await get(s,"/api/v3/market/candles",{"category":"USDT-FUTURES","symbol":sym,"interval":"1m","limit":"100"})
    book=ob.get("data",{});asks=book.get("a",[]);bids=book.get("b",[])
    def depth(levels):
     return round(sum(n(p)*n(q) for p,q in levels if mid and abs(n(p)/mid-1)<=.005),3)
    add(O,{"at":iso(),"symbol":sym,"base_coin":m.get("baseCoin"),"turnover24h_usdt":turnover,"last":n(t.get("lastPrice")),"mark":n(t.get("markPrice")),"index":n(t.get("indexPrice")),"funding":n(t.get("fundingRate")),"open_interest":n(t.get("openInterest")),"spread_bps":spread,"depth_0_5pct_bid_usdt":depth(bids),"depth_0_5pct_ask_usdt":depth(asks),"orderbook_ts":book.get("ts"),"candle_rows":len(candles.get("data",[])),"market_cap":"UNVERIFIED"})
    for strat,direction,reason in strategy(candles.get("data",[]),mid,spread,n(m.get("takerFeeRate"))):
     sid=f"{sym}:{strat}:{candles['data'][-1][0]}"
     seen=st.setdefault("signal_ids",[])
     if sid in seen:continue
     seen.append(sid);seen[:]=seen[-3000:];signals+=1
     add(E,{"type":"signal","id":sid,"at":iso(),"symbol":sym,"strategy":strat,"direction":direction,"reason":reason,"reference_entry":mid,"estimated_round_trip_cost_bps":spread+2*n(m.get("takerFeeRate"))*10000,"status":"unverified hypothesis"})
     q=read(Q,[])
     for mins in (5,15,30):q.append({"id":sid,"symbol":sym,"strategy":strat,"direction":direction,"entry":mid,"cost":spread+2*n(m.get("takerFeeRate"))*10000,"due":now().timestamp()+mins*60,"horizon_min":mins})
     Q.write_text(json.dumps(q,indent=2))
  except Exception as ex:errors.append(str(ex))
  # Evaluate due signals using latest ticker reference price (not fill).
  q=read(Q,[]);keep=[]
  for x in q:
   px=current.get(x["symbol"])
   if px and now().timestamp()>=x["due"]:
    gross=(px/x["entry"]-1)*10000 if x["direction"]=="LONG" else (x["entry"]/px-1)*10000
    add(E,{"type":"forward_reference_outcome","at":iso(),**x,"exit_reference":px,"gross_bps":gross,"estimated_net_bps":gross-x["cost"],"caveat":"Reference-price result, not executable fill; excludes funding and changing impact."})
   else:keep.append(x)
  Q.write_text(json.dumps(keep,indent=2))
  newposts=await posts(s)
 if errors:add(R/"collection_errors.jsonl",{"at":iso(),"error":";".join(errors)[:800]})
 st["cycles"]=st.get("cycles",0)+1;st["last_at"]=iso();st["signals"]=st.get("signals",0)+signals;st["posts"]=st.get("posts",0)+newposts;st["errors"]=st.get("errors",0)+len(errors);st["symbols_last_cycle"]=len(current)
 S.write_text(json.dumps(st,indent=2))
 print(json.dumps({"cycle":st["cycles"],"symbols":len(current),"signals":signals,"new_posts":newposts,"errors":len(errors),"ends":st["ends_at_utc"]}))
def main():
 p=argparse.ArgumentParser();p.add_argument("action",choices=["start","collect","status"]);a=p.parse_args()
 if a.action=="start":
  R.mkdir(parents=True,exist_ok=True);end=now().timestamp()+86400
  st={"active":True,"started_at_utc":iso(),"end_epoch":end,"ends_at_utc":datetime.fromtimestamp(end,timezone.utc).isoformat(),"cycles":0,"signals":0,"posts":0,"errors":0,"signal_ids":[]}
  S.write_text(json.dumps(st,indent=2));Q.write_text("[]");print("Started 24-hour session until "+st["ends_at_utc"])
 elif a.action=="collect":asyncio.run(collect())
 else:print(json.dumps(read(S,{"active":False}),indent=2))
if __name__=="__main__":main()
