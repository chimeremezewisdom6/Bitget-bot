"""Authenticated, read-only Bitget research for gradual trends lasting 2+ hours."""
import asyncio, base64, hashlib, hmac, json, math, os, statistics, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import aiohttp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"reports/daily_research"
BITGET="https://api.bitget.com"
CATEGORY="USDT-FUTURES"
LIMIT=200
DURATION=120
MIN_TREND_PCT=4.0
SPEED_MULTIPLE=4.0

def num(v, default=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except (TypeError,ValueError):
        return default

def credentials():
    def first(*keys):
        for key in keys:
            value=os.getenv(key,"").strip()
            if value: return value
        return ""
    return (first("BITGET_API_KEY","BITGET_KEY"),
            first("BITGET_API_SECRET","BITGET_SECRET_KEY","BITGET_SECRET"),
            first("BITGET_API_PASSPHRASE","BITGET_PASSPHRASE","BITGET_API_PASSWORD","BITGET_PASSWORD"))

def signed_headers(path, params=None):
    key,secret,phrase=credentials()
    if not all((key,secret,phrase)):
        raise RuntimeError("Bitget API credentials missing from GitHub Actions Secrets.")
    query=urlencode(sorted((params or {}).items()))
    ts=str(int(time.time()*1000))
    request_path=path+(("?"+query) if query else "")
    message=ts+"GET"+request_path
    sign=base64.b64encode(hmac.new(secret.encode(),message.encode(),hashlib.sha256).digest()).decode()
    return {"ACCESS-KEY":key,"ACCESS-SIGN":sign,"ACCESS-TIMESTAMP":ts,
            "ACCESS-PASSPHRASE":phrase,"locale":"en-US","Content-Type":"application/json"},query

async def get(session,path,params=None,auth=False):
    headers=None
    if auth:
        headers,query=signed_headers(path,params)
        url=BITGET+path+(("?"+query) if query else "")
        params=None
    else: url=BITGET+path
    error=None
    for attempt in range(4):
        try:
            async with session.get(url,params=params,headers=headers,timeout=30) as response:
                if response.status==429 or response.status>=500: raise RuntimeError("Bitget HTTP "+str(response.status))
                response.raise_for_status()
                payload=await response.json()
                if payload.get("code")!="00000":
                    raise RuntimeError("Bitget "+str(payload.get("code"))+": "+str(payload.get("msg")))
                return payload.get("data",[])
        except Exception as exc:
            error=exc
            if attempt<3: await asyncio.sleep(1*(2**attempt))
    raise RuntimeError(str(error))

def normalize(raw):
    by={}
    for r in raw or []:
        try:
            if len(r)>=7:
                ts=int(r[0])
                by[ts]={"ts":ts,"o":num(r[1]),"h":num(r[2]),"l":num(r[3]),
                        "c":num(r[4]),"base_volume":num(r[5]),"quote_volume":num(r[6])}
        except (ValueError,TypeError,IndexError): pass
    return [by[k] for k in sorted(by)]

def directional_pct(start,end,side):
    if start<=0 or end<=0: return 0.0
    return ((end/start)-1)*100*(1 if side=="LONG" else -1)

def analyze(symbol,rows,start_ms,end_ms):
    rows=[r for r in rows if start_ms<=r["ts"] and r["ts"]+60000<=end_ms]
    events=[]
    diagnostics={"breakout_2h_hold":0,"return_at_least_4pct":0,"speed_rule_pass":0,"rejected_below_4pct":0,"rejected_speed_ratio":0}
    near_misses=[]
    last_i=-DURATION
    for i in range(60,len(rows)-DURATION+1):
        if i-last_i<DURATION: continue
        sample=rows[i-60:i+DURATION]
        if len(sample)!=180 or any(sample[j]["ts"]-sample[j-1]["ts"]!=60000 for j in range(1,180)): continue
        prior=rows[i-60:i]
        high=max(x["h"] for x in prior); low=min(x["l"] for x in prior)
        first=rows[i]
        if first["c"]>high: side,boundary="LONG",high
        elif first["c"]<low: side,boundary="SHORT",low
        else: continue
        future=rows[i:i+DURATION]
        if any((x["c"]<=boundary if side=="LONG" else x["c"]>=boundary) for x in future): continue
        last_i=i  # Avoid counting overlapping starts inside the same confirmed 2h move.
        diagnostics["breakout_2h_hold"]+=1
        total=directional_pct(first["c"],future[-1]["c"],side)
        # Check every rolling 10m interval, not only the opening 10m.
        moves=[directional_pct(future[j]["o"],future[j+9]["c"],side) for j in range(DURATION-9)]
        max10=max([0.0]+moves)
        first10=directional_pct(future[0]["o"],future[9]["c"],side)
        # User rule compares the full two-hour move with the FIRST 10 minutes.
        # Later rolling 10m bursts are measured and reported, not used to change that rule.
        speed_move=abs(first10)
        ratio=(total/speed_move) if speed_move>0 else None
        if total<MIN_TREND_PCT:
            diagnostics["rejected_below_4pct"]+=1
            near_misses.append({"symbol":symbol,"direction":side,"start_timestamp_ms":first["ts"],"start_close":first["c"],"two_hour_move_pct":round(total,5),"first_10m_move_pct":round(first10,5),"fastest_rolling_10m_move_pct":round(max10,5),"ratio":round(ratio,4) if ratio is not None else None,"rejection":"TWO_HOUR_MOVE_BELOW_4_PERCENT"})
            continue
        diagnostics["return_at_least_4pct"]+=1
        if ratio is None or ratio<SPEED_MULTIPLE:
            diagnostics["rejected_speed_ratio"]+=1
            near_misses.append({"symbol":symbol,"direction":side,"start_timestamp_ms":first["ts"],"start_close":first["c"],"two_hour_move_pct":round(total,5),"first_10m_move_pct":round(first10,5),"fastest_rolling_10m_move_pct":round(max10,5),"ratio":round(ratio,4) if ratio is not None else None,"rejection":"FAST_10M_MOVE_EXCEEDED_ONE_QUARTER_OF_2H_MOVE"})
            continue
        diagnostics["speed_rule_pass"]+=1
        match=lambda x: x["c"]>x["o"] if side=="LONG" else x["c"]<x["o"]
        aligned15=sum(match(x) for x in future[:15])
        aligned30=sum(match(x) for x in future[:30])
        aligned120=sum(match(x) for x in future)
        baseline=sum(x["quote_volume"] for x in prior[-20:])/20
        turn10=sum(x["quote_volume"] for x in future[:10])/10
        turn30=sum(x["quote_volume"] for x in future[:30])/30
        fav=[]; adverse=[]
        for x in future:
            if side=="LONG":
                fav.append((x["h"]/first["c"]-1)*100); adverse.append((x["l"]/first["c"]-1)*100)
            elif x["l"]>0 and x["h"]>0:
                fav.append((first["c"]/x["l"]-1)*100); adverse.append((first["c"]/x["h"]-1)*100)
        events.append({
            "symbol":symbol,"direction":side,
            "start_utc":datetime.fromtimestamp(first["ts"]/1000,timezone.utc).isoformat(),
            "start_timestamp_ms":first["ts"],"start_close":first["c"],"breakout_level":boundary,
            "duration_minutes":120,"end_120m_close":future[-1]["c"],
            "direction_adjusted_120m_return_pct":round(total,5),
            "first_10m_directional_move_pct":round(first10,5),
            "largest_rolling_10m_directional_move_pct":round(max10,5),
            "two_hour_to_first10m_ratio":round(ratio,4),
            "direction_matching_candles_first15m":aligned15,
            "direction_matching_candles_first30m":aligned30,
            "direction_matching_candles_120m":aligned120,
            "direction_matching_pct_120m":round(aligned120/120*100,2),
            "first10m_quote_turnover_vs_prior20m":round(turn10/baseline,4) if baseline else None,
            "first30m_quote_turnover_vs_prior20m":round(turn30/baseline,4) if baseline else None,
            "max_favorable_excursion_pct":round(max(fav),5) if fav else None,
            "max_adverse_excursion_pct":round(min(adverse),5) if adverse else None,
            "historical_open_interest_change_pct":None,
            "definition":"120m breakout hold, >=4% directional return, and >=4x the absolute directional move in the first 10m"
        })
    return events,diagnostics,near_misses

def oi_points(payload):
    data=payload.get("list",[]) if isinstance(payload,dict) else (payload if isinstance(payload,list) else [])
    result=[]
    for x in data or []:
        try:
            ts=int(x.get("timestamp",x.get("ts",0)))
            val=num(x.get("openInterestValue")) or num(x.get("openInterest"))
            if ts and val>0: result.append((ts,val))
        except (AttributeError,TypeError,ValueError): pass
    return sorted(result)

def oi_change(series,start,end):
    if len(series)<2: return None
    a=min(series,key=lambda x:abs(x[0]-start)); b=min(series,key=lambda x:abs(x[0]-end))
    if abs(a[0]-start)>600000 or abs(b[0]-end)>600000 or b[0]<=a[0]: return None
    return round((b[1]/a[1]-1)*100,5)

async def enrich(session,symbol,events,sem):
    async with sem:
        out={"symbol":symbol,"oi_points_returned":0,"current_funding_rate":None,
             "current_orderbook_imbalance_pct":None,"notes":[]}
        try:
            raw=await get(session,"/api/v3/market/open-interest-history",{"symbol":symbol,"period":"5m"})
            series=oi_points(raw); out["oi_points_returned"]=len(series)
            changes=[]
            for e in events:
                change=oi_change(series,e["start_timestamp_ms"],e["start_timestamp_ms"]+120*60000)
                e["historical_open_interest_change_pct"]=change
                if change is not None: changes.append(change)
            out["historical_oi_changes_found"]=len(changes)
            if not changes: out["notes"].append("OI endpoint did not return observations near both event boundaries; historical OI left blank.")
        except Exception as exc:
            out["notes"].append("OI history unavailable: "+str(exc)[:120])
        try:
            fund=await get(session,"/api/v3/market/current-fund-rate",{"category":CATEGORY,"symbol":symbol})
            if isinstance(fund,list) and fund: out["current_funding_rate"]=num(fund[0].get("fundingRate"),None)
            elif isinstance(fund,dict): out["current_funding_rate"]=num(fund.get("fundingRate"),None)
            out["notes"].append("Funding is a current snapshot, not historical event-time funding.")
        except Exception as exc: out["notes"].append("Current funding unavailable: "+str(exc)[:100])
        try:
            book=await get(session,"/api/v3/market/orderbook",{"category":CATEGORY,"symbol":symbol,"limit":"50"})
            if isinstance(book,list) and book: book=book[0]
            if isinstance(book,dict):
                bid=sum(num(x[1]) for x in book.get("bids",[]) if len(x)>1)
                ask=sum(num(x[1]) for x in book.get("asks",[]) if len(x)>1)
                if bid+ask: out["current_orderbook_imbalance_pct"]=round((bid-ask)/(bid+ask)*100,3)
            out["notes"].append("Order book is a current snapshot, not historical event-time depth.")
        except Exception as exc: out["notes"].append("Current order book unavailable: "+str(exc)[:100])
        return out

async def authenticate(session):
    # Only signed account-info and fee reads. No balances, positions, or order endpoints.
    info=await get(session,"/api/v3/account/info",auth=True)
    permission=info.get("permType","unknown") if isinstance(info,dict) else "unknown"
    try:
        fees=await get(session,"/api/v3/account/all-fee-rate",{"category":CATEGORY},auth=True)
        fee_status="AVAILABLE" if fees else "EMPTY_RESPONSE"
    except Exception as exc: fee_status="UNAVAILABLE: "+str(exc)[:150]
    return {"authenticated":True,"permission_type":permission,"fee_schedule_status":fee_status,
            "scope":"Signed account-info and fee-rate reads only; no balances, positions, orders, or withdrawals."}

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    end_ms=(int(datetime.now(timezone.utc).timestamp()*1000)//60000)*60000
    start_ms=end_ms-24*60*60000; midpoint=start_ms+12*60*60000
    timeout=aiohttp.ClientTimeout(total=50,connect=15)
    async with aiohttp.ClientSession(timeout=timeout,headers={"User-Agent":"Bitget-Genuine-Trend-Research/2.0"}) as s:
        auth=await authenticate(s)
        instruments,tickers=await asyncio.gather(
            get(s,"/api/v3/market/instruments",{"category":CATEGORY}),
            get(s,"/api/v3/market/tickers",{"category":CATEGORY}))
        online={x.get("symbol") for x in instruments if x.get("status")=="online"
                and (x.get("type")=="perpetual" or x.get("instrumentType")=="perpetual")
                and x.get("symbolType","crypto")=="crypto"}
        universe=sorted([x for x in tickers if x.get("symbol") in online],
                        key=lambda x:num(x.get("turnover24h")),reverse=True)[:LIMIT]
        sem=asyncio.Semaphore(6)
        async def fetch_one(t):
            symbol=t["symbol"]
            async with sem:
                async def page(a,b):
                    return await get(s,"/api/v3/market/candles",{"category":CATEGORY,"symbol":symbol,
                        "interval":"1m","startTime":str(a),"endTime":str(b),"limit":"1000"})
                try:
                    a,b=await asyncio.gather(page(start_ms,midpoint),page(midpoint,end_ms))
                    rows=normalize(a+b)
                    if len(rows)<120: raise RuntimeError("Only "+str(len(rows))+" candles returned")
                    return symbol,num(t.get("turnover24h")),rows,None
                except Exception as exc: return symbol,num(t.get("turnover24h")),[],str(exc)[:200]
        fetched=await asyncio.gather(*(fetch_one(t) for t in universe))
        events=[]; coverage=[]; errors=[]; diagnostic_totals={"breakout_2h_hold":0,"return_at_least_4pct":0,"speed_rule_pass":0,"rejected_below_4pct":0,"rejected_speed_ratio":0}; near_misses=[]
        for symbol,turnover,rows,error in fetched:
            if rows:
                found,diag,near=analyze(symbol,rows,start_ms,end_ms)
                for key in diagnostic_totals: diagnostic_totals[key]+=diag[key]
                near_misses.extend(near)
            else:
                found=[]; diag={key:0 for key in diagnostic_totals}
            events.extend(found)
            if error: errors.append({"symbol":symbol,"error":error})
            coverage.append({"symbol":symbol,"turnover24h_usdt":turnover,"closed_1m_candles":len(rows),
                "qualifying_trends":len(found),"breakout_2h_hold_candidates":diag["breakout_2h_hold"],"rejected_below_4pct":diag["rejected_below_4pct"],"rejected_speed_ratio":diag["rejected_speed_ratio"],"long":sum(e["direction"]=="LONG" for e in found),
                "short":sum(e["direction"]=="SHORT" for e in found),"error":error})
        grouped={}
        for e in events: grouped.setdefault(e["symbol"],[]).append(e)
        enrich_sem=asyncio.Semaphore(3)
        enrichment=await asyncio.gather(*(enrich(s,symbol,ev,enrich_sem) for symbol,ev in grouped.items()))
        enrich_map={x["symbol"]:x for x in enrichment}
        for e in events:
            extra=enrich_map.get(e["symbol"],{})
            e["current_funding_rate"]=extra.get("current_funding_rate")
            e["current_orderbook_imbalance_pct"]=extra.get("current_orderbook_imbalance_pct")
            e["market_context_notes"]=extra.get("notes",[])

    returns=[e["direction_adjusted_120m_return_pct"] for e in events]
    lines=[
      "# Bitget authenticated 24-hour genuine-trend backtest","",
      "- Generated UTC: "+datetime.now(timezone.utc).isoformat(),
      "- Window UTC: "+datetime.fromtimestamp(start_ms/1000,timezone.utc).isoformat()+" to "+datetime.fromtimestamp(end_ms/1000,timezone.utc).isoformat(),
      "- Bitget API key authentication: SUCCESS",
      "- Key permission type: "+str(auth["permission_type"]),
      "- Account fee schedule: "+str(auth["fee_schedule_status"]),
      "- Access scope: "+auth["scope"],
      "- Universe: top "+str(len(universe))+" online crypto USDT perpetuals by 24h turnover.",
      "- Coverage: "+str(sum(not x["error"] for x in coverage))+"/"+str(len(universe))+" symbols; "+format(sum(x["closed_1m_candles"] for x in coverage),",")+" closed 1m candles; "+str(len(errors))+" fetch errors.",
      "- 2h breakout-and-hold candidates before the 4%/speed filters: "+str(diagnostic_totals["breakout_2h_hold"]),
      "- Candidates reaching 4% over 2h: "+str(diagnostic_totals["return_at_least_4pct"]),
      "- Rejected below 4%: "+str(diagnostic_totals["rejected_below_4pct"]),
      "- Rejected by the 4x speed rule: "+str(diagnostic_totals["rejected_speed_ratio"]),
      "- Qualifying gradual trends: "+str(len(events))+" (LONG "+str(sum(e["direction"]=="LONG" for e in events))+", SHORT "+str(sum(e["direction"]=="SHORT" for e in events))+").",
      "",
      "## Exact trend rules",
      "1. A closed 1m candle closes above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT).",
      "2. Every subsequent closed 1m candle remains outside that breakout level for 120 complete minutes.",
      "3. Direction-adjusted net movement from breakout close to the 120th-minute close is at least 4%.",
      "4. The 120m directional move is at least 4 times the absolute directional move in the FIRST 10 minutes. The largest rolling 10m move later in the trend is measured separately as a diagnostic, not used to reject the trend.",
      "5. LONG and SHORT are evaluated separately; gaps and incomplete candles invalidate a sample.",
      "",
      "## Aggregate findings",
      ("- Mean qualifying 2h directional return: %.4f%%" % statistics.mean(returns)) if returns else "- No events passed all rules.",
      ("- Median qualifying 2h directional return: %.4f%%" % statistics.median(returns)) if returns else "",
      ("- Mean 2h-to-first-10m ratio: %.3fx" % statistics.mean([e["two_hour_to_first10m_ratio"] for e in events])) if events else "",
      "",
      "## What the data says fuels the move",
      "- Persistence: 120m breakout-level hold, direction-matching candle counts, and maximum adverse/favorable excursion.",
      "- Participation: first-10m and first-30m quote-turnover acceleration versus the 20m before the breakout.",
      "- Historical open interest: reported only when Bitget's returned 5m observations cover both event boundaries; otherwise left blank.",
      "- Funding and order book: current snapshots for qualifying symbols only. They are not falsely described as historical causes.",
      "- Aggressive buyer/seller dominance: not inferred from OHLCV candles; no unsupported taker-side conclusion.",
      "",
      "## Qualifying events",
      "| Symbol | Side | Start UTC | 2h move % | First 10m % | Fastest 10m % | Ratio | 15m aligned | 120m aligned | First 10m turnover x | Historical OI % |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for e in sorted(events,key=lambda x:x["direction_adjusted_120m_return_pct"],reverse=True):
        lines.append("| %s | %s | %s | %.4f | %.4f | %.4f | %.2fx | %s/15 | %s/120 | %s | %s |" % (
            e["symbol"],e["direction"],e["start_utc"],e["direction_adjusted_120m_return_pct"],
            e["first_10m_directional_move_pct"],e["largest_rolling_10m_directional_move_pct"],
            e["two_hour_to_first10m_ratio"],e["direction_matching_candles_first15m"],
            e["direction_matching_candles_120m"],e["first10m_quote_turnover_vs_prior20m"],
            e["historical_open_interest_change_pct"]))
    lines += ["","## Per-coin coverage","| Symbol | Candles | Trends | LONG | SHORT | Status |",
              "|---|---:|---:|---:|---:|---|"]
    for c in sorted(coverage,key=lambda x:x["qualifying_trends"],reverse=True):
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            c["symbol"],c["closed_1m_candles"],c["qualifying_trends"],c["long"],c["short"],
            ("ERROR: "+c["error"]) if c["error"] else "OK"))
    lines += ["","## Limitations",
      "- Historical research only; not current entry signals or a profitability claim.",
      "- Breakout/hold is a defined proxy and can miss trends without a 60m range break or with a brief retest.",
      "- The four-times filter compares the 2h movement with the first 10m movement. Later fast bursts are reported separately.",
      "- Historical OI, funding, order-book depth and taker-side history may not cover past events. Missing evidence is not fabricated.",
      "- Returns exclude fees, spread, slippage, funding payments and execution latency. No orders were placed.",
      "- Top 200 means the highest 24h-turnover online crypto USDT perpetuals at test time.",""]
    (OUT/"bitget_24h_2h_trend_backtest.md").write_text("\n".join(lines),encoding="utf-8")
    (OUT/"bitget_24h_2h_trend_events.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
    (OUT/"bitget_24h_2h_trend_coin_summary.json").write_text(json.dumps({
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),"window_start_ms":start_ms,"window_end_ms":end_ms,
        "authentication":auth,"symbols_requested":len(universe),"symbols_successful":sum(not x["error"] for x in coverage),
        "symbols_failed":len(errors),"closed_1m_candles":sum(x["closed_1m_candles"] for x in coverage),
        "qualifying_trends":len(events),"diagnostics":diagnostic_totals,"near_misses":near_misses[:500],"long":sum(e["direction"]=="LONG" for e in events),
        "short":sum(e["direction"]=="SHORT" for e in events),"coverage":coverage,"errors":errors,
        "enrichment":enrichment},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"authenticated":True,"permission_type":auth["permission_type"],
        "symbols_requested":len(universe),"symbols_successful":sum(not x["error"] for x in coverage),
        "symbols_failed":len(errors),"closed_1m_candles":sum(x["closed_1m_candles"] for x in coverage),
        "qualifying_trends":len(events),"long":sum(e["direction"]=="LONG" for e in events),
        "short":sum(e["direction"]=="SHORT" for e in events),
        "report":"reports/daily_research/bitget_24h_2h_trend_backtest.md"},indent=2))

if __name__=="__main__":
    asyncio.run(main())
