"""Enrich 14-day breakout events with historical derivatives positioning/flow.

Public market-data endpoints only. This script never accesses order endpoints.
It joins only observations at or before each event to avoid look-ahead leakage.
"""
import asyncio, json, math, statistics, time
from pathlib import Path
from datetime import datetime, timezone
import aiohttp

BASE="https://api.bitget.com"
ROOT=Path(__file__).resolve().parent
R=ROOT/"reports/daily_research"
EVENTS=R/"bitget_14d_trend_fuel_events.jsonl"
SUMMARY=R/"bitget_14d_trend_fuel_summary.json"
OUT=R/"bitget_14d_derivatives_fuel_report.md"
JSON_OUT=R/"bitget_14d_derivatives_fuel_events.jsonl"

def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):
        return None

class Gate:
    def __init__(self, delay):
        self.delay=delay; self.lock=asyncio.Lock(); self.last=0
    async def wait(self):
        async with self.lock:
            d=self.delay-(time.monotonic()-self.last)
            if d>0: await asyncio.sleep(d)
            self.last=time.monotonic()

async def request(session, path, params, gates):
    gate=gates[path]
    last=None
    for attempt in range(5):
        await gate.wait()
        try:
            async with session.get(BASE+path,params=params) as r:
                if r.status==429 or r.status>=500:
                    raise RuntimeError("HTTP "+str(r.status))
                r.raise_for_status()
                payload=await r.json()
                if payload.get("code")!="00000":
                    raise RuntimeError(str(payload.get("code"))+" "+str(payload.get("msg")))
                return payload.get("data")
        except Exception as e:
            last=e
            if attempt<4: await asyncio.sleep(min(12,1.5*(2**attempt)))
    raise RuntimeError(str(last))

def rows_of(data, key):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        value=data.get(key)
        if isinstance(value,list): return value
        for k in ("list","resultList","data"):
            if isinstance(data.get(k),list): return data[k]
    return []

def timed_rows(rows, ts_keys):
    out=[]
    for x in rows:
        if not isinstance(x,dict): continue
        ts=next((num(x.get(k)) for k in ts_keys if num(x.get(k)) is not None),None)
        if ts is not None: out.append((int(ts),x))
    return sorted(out)

def asof(rows, timestamp, max_age_ms):
    eligible=[(t,x) for t,x in rows if t<=timestamp and timestamp-t<=max_age_ms]
    return eligible[-1] if eligible else (None,None)

async def fetch_symbol(session, symbol, gates, sem):
    async with sem:
        specs=[
            ("/api/v3/market/open-interest-history",{"symbol":symbol,"period":"5m"},"list"),
            ("/api/v3/market/futures-active-buy-sell",{"symbol":symbol,"period":"5m"},"data"),
            ("/api/v3/market/futures-long-short",{"symbol":symbol,"period":"5m"},"data"),
            ("/api/v3/market/history-fund-rate",{"category":"USDT-FUTURES","symbol":symbol,"limit":"100","cursor":"1"},"resultList"),
        ]
        result={}
        for path,params,key in specs:
            try:
                data=await request(session,path,params,gates)
                result[path]=rows_of(data,key)
            except Exception as e:
                result[path]={"error":str(e)[:180]}
        return symbol,result

def summarize(values):
    values=[v for v in values if v is not None and math.isfinite(v)]
    if not values: return {"n":0,"median":None,"mean":None}
    return {"n":len(values),"median":round(statistics.median(values),6),"mean":round(statistics.mean(values),6)}

async def main():
    if not EVENTS.exists() or EVENTS.stat().st_size==0:
        raise RuntimeError("Full breakout event file is missing/empty; run the 14-day backtest first.")
    events=[json.loads(x) for x in EVENTS.read_text().splitlines() if x.strip()]
    symbols=sorted({e["symbol"] for e in events if e.get("symbol")})
    gates={
        "/api/v3/market/open-interest-history":Gate(0.15),
        "/api/v3/market/futures-active-buy-sell":Gate(1.05),
        "/api/v3/market/futures-long-short":Gate(1.05),
        "/api/v3/market/history-fund-rate":Gate(0.12),
    }
    timeout=aiohttp.ClientTimeout(total=35,connect=12)
    connector=aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(timeout=timeout,connector=connector) as session:
        sem=asyncio.Semaphore(12)
        fetched=await asyncio.gather(*(fetch_symbol(session,s,gates,sem) for s in symbols))
    by_symbol=dict(fetched)
    enriched=[]
    source_counts={k:0 for k in gates}
    errors={k:0 for k in gates}
    for symbol,data in by_symbol.items():
        for path,value in data.items():
            if isinstance(value,dict) and "error" in value: errors[path]+=1
            elif value: source_counts[path]+=1
    for e in events:
        symbol=e["symbol"]; ts=int(e["timestamp_ms"]); d=by_symbol.get(symbol,{})
        oi=timed_rows(d.get("/api/v3/market/open-interest-history",[]) if isinstance(d.get("/api/v3/market/open-interest-history"),list) else [],("timestamp","ts"))
        taker=timed_rows(d.get("/api/v3/market/futures-active-buy-sell",[]) if isinstance(d.get("/api/v3/market/futures-active-buy-sell"),list) else [],("ts","timestamp"))
        ls=timed_rows(d.get("/api/v3/market/futures-long-short",[]) if isinstance(d.get("/api/v3/market/futures-long-short"),list) else [],("ts","timestamp"))
        fund=timed_rows(d.get("/api/v3/market/history-fund-rate",[]) if isinstance(d.get("/api/v3/market/history-fund-rate"),list) else [],("fundingRateTimestamp","ts"))
        oi_t,oi_x=asof(oi,ts,30*60*1000)
        taker_t,taker_x=asof(taker,ts,15*60*1000)
        ls_t,ls_x=asof(ls,ts,30*60*1000)
        fund_t,fund_x=asof(fund,ts,10*24*60*60*1000)
        def previous(rows,t):
            xs=[x for x in rows if x[0]<t]
            return xs[-1][1] if xs else None
        oi_prev=previous(oi,oi_t) if oi_t else None
        oi_now=num((oi_x or {}).get("openInterestValue", (oi_x or {}).get("openInterest")))
        oi_old=num((oi_prev or {}).get("openInterestValue", (oi_prev or {}).get("openInterest")))
        oi_change=((oi_now/oi_old)-1)*100 if oi_now is not None and oi_old not in (None,0) else None
        buy=num((taker_x or {}).get("buyVolume")); sell=num((taker_x or {}).get("sellVolume"))
        taker_imbalance=(buy-sell)/(buy+sell) if buy is not None and sell is not None and buy+sell>0 else None
        ratio=num((ls_x or {}).get("longShortRatio"))
        funding=num((fund_x or {}).get("fundingRate"))
        enriched.append({
            "symbol":symbol,"direction":e.get("direction"),"label":e.get("label"),
            "timestamp_ms":ts,"two_hour_return_pct":e.get("two_hour_return_pct"),
            "open_interest_timestamp_ms":oi_t,"open_interest_value":oi_now,
            "open_interest_change_pct":oi_change,
            "taker_flow_timestamp_ms":taker_t,"taker_buy_volume":buy,"taker_sell_volume":sell,
            "taker_imbalance":taker_imbalance,
            "long_short_timestamp_ms":ls_t,"long_short_ratio":ratio,
            "funding_timestamp_ms":fund_t,"funding_rate":funding,
        })
    JSON_OUT.write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in enriched))
    groups={}
    for label in ("GRADUAL_TREND","FAST_SPIKE","FAILED_OR_WEAK"):
        rows=[x for x in enriched if x.get("label")==label]
        groups[label]={
            "events":len(rows),
            "OI change %":summarize([x["open_interest_change_pct"] for x in rows]),
            "taker imbalance":summarize([x["taker_imbalance"] for x in rows]),
            "long/short ratio":summarize([x["long_short_ratio"] for x in rows]),
            "funding rate":summarize([x["funding_rate"] for x in rows]),
            "OI matched":sum(x["open_interest_timestamp_ms"] is not None for x in rows),
            "taker matched":sum(x["taker_flow_timestamp_ms"] is not None for x in rows),
            "long/short matched":sum(x["long_short_timestamp_ms"] is not None for x in rows),
            "funding matched":sum(x["funding_timestamp_ms"] is not None for x in rows),
        }
    lines=[
        "# Bitget 14-day derivatives fuel enrichment",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Events: {len(events)}; symbols: {len(symbols)}",
        "",
        "Only observations timestamped at or before the breakout are joined. OI/taker/long-short are accepted only when recent enough (30m/15m/30m); funding may be up to 10 days old because settlement intervals vary.",
        "A missing match is reported as missing, never filled with a later observation.",
        "",
        "## Coverage by source",
        json.dumps({"successful_symbols":source_counts,"symbol_errors":errors},indent=2),
        "",
        "## Event groups",
        json.dumps(groups,indent=2),
        "",
        "## Interpretation guardrails",
        "- Open-interest increase means aggregate positions expanded; it does not identify whether longs or shorts initiated them.",
        "- Taker imbalance is based on the API's buyVolume/sellVolume buckets; validate the endpoint's classification before treating it as aggressor-side flow.",
        "- Long/short ratio is crowd positioning, not proof of new buying or selling.",
        "- Funding is a positioning/carry context variable, not a directional signal by itself.",
        "- Endpoint history depth may be shorter than the full 14-day candle window. Coverage counts expose this.",
        "- This is observational research, not a causal test or trading recommendation.",
        "",
        "Raw event-level joins: bitget_14d_derivatives_fuel_events.jsonl",
    ]
    OUT.write_text("\n".join(lines)+"\n")
    print(json.dumps({"status":"complete","events":len(events),"symbols":len(symbols),"groups":groups},indent=2))

if __name__=="__main__":
    asyncio.run(main())
