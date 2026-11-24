"""24h, 1m Bitget USDT-perpetual backtest for trends lasting at least 2 hours.
Public market data only. No account access and no orders.
"""
import asyncio, json, math
from datetime import datetime, timezone
from pathlib import Path
import aiohttp

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports/daily_research"
BITGET = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
LIMIT = 200
CONCURRENCY = 10
MIN_DURATION = 120


def num(x, default=0.0):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


async def get(session, path, params=None):
    last=None
    for attempt in range(4):
        try:
            async with session.get(BITGET+path, params=params, timeout=25) as r:
                if r.status == 429 or r.status >= 500:
                    raise RuntimeError(f"HTTP {r.status}")
                r.raise_for_status()
                data=await r.json()
                if data.get("code") != "00000":
                    raise RuntimeError(f"Bitget {data.get('code')}: {data.get('msg')}")
                return data.get("data", [])
        except Exception as e:
            last=e
            if attempt<3: await asyncio.sleep(0.8*(2**attempt))
    raise RuntimeError(f"{path}: {last}")


def normalize(raw):
    by={}
    for r in raw:
        try:
            if len(r)>=7:
                ts=int(r[0])
                by[ts]={"ts":ts,"o":num(r[1]),"h":num(r[2]),"l":num(r[3]),
                        "c":num(r[4]),"v":num(r[5]),"q":num(r[6])}
        except (TypeError,ValueError,IndexError):
            pass
    return [by[k] for k in sorted(by)]


def backtest(symbol, rows, start_ms, end_ms):
    # Retain only fully closed, gap-free 1m candles inside the requested window.
    rows=[r for r in rows if start_ms <= r["ts"] and r["ts"]+60000 <= end_ms]
    events=[]
    last_start=-120
    for i in range(60, len(rows)-MIN_DURATION):
        if i-last_start < MIN_DURATION: continue
        window=rows[i-60:i+MIN_DURATION]
        if len(window)!=60+MIN_DURATION: continue
        if any(window[j]["ts"]-window[j-1]["ts"]!=60000 for j in range(1,len(window))): continue
        prior=rows[i-60:i]
        ceiling=max(x["h"] for x in prior)
        floor=min(x["l"] for x in prior)
        start=rows[i]
        if start["c"]>ceiling:
            side="LONG"; boundary=ceiling
        elif start["c"]<floor:
            side="SHORT"; boundary=floor
        else:
            continue
        future=rows[i:i+MIN_DURATION]
        # A breakout remains valid while closes hold outside the broken 60m range.
        invalid=None
        for k,x in enumerate(future):
            if (side=="LONG" and x["c"]<=boundary) or (side=="SHORT" and x["c"]>=boundary):
                invalid=k
                break
        duration=MIN_DURATION if invalid is None else invalid
        if duration<MIN_DURATION:
            continue
        start_price=start["c"]
        end_price=future[-1]["c"]
        ret=((end_price/start_price)-1)*100 if side=="LONG" and start_price else (
            (start_price/end_price)-1)*100 if side=="SHORT" and end_price else 0.0)
        aligned=sum(x["c"]>x["o"] if side=="LONG" else x["c"]<x["o"] for x in future)
        first15=future[:15]
        aligned15=sum(x["c"]>x["o"] if side=="LONG" else x["c"]<x["o"] for x in first15)
        turnover15=sum(x["q"] for x in first15)/15
        baseline=sum(x["q"] for x in prior[-20:])/20
        favorable=max((((x["h"]/start_price)-1)*100 if side=="LONG" else ((start_price/x["l"])-1)*100)
                      for x in future if (x["l"]>0 if side=="SHORT" else x["h"]>0))
        adverse=min((((x["l"]/start_price)-1)*100 if side=="LONG" else ((start_price/x["h"])-1)*100)
                    for x in future if (x["h"]>0 if side=="SHORT" else x["l"]>0))
        events.append({
            "symbol":symbol,"direction":side,
            "start_utc":datetime.fromtimestamp(start["ts"]/1000,timezone.utc).isoformat(),
            "start_timestamp_ms":start["ts"],"start_close":start_price,
            "prior_60m_break_level":boundary,"duration_minutes":duration,
            "end_120m_close":end_price,"direction_adjusted_120m_return_pct":round(ret,4),
            "direction_matching_candles_120m":aligned,
            "direction_matching_pct_120m":round(aligned/120*100,2),
            "direction_matching_candles_first15m":aligned15,
            "direction_matching_pct_first15m":round(aligned15/15*100,2),
            "first15m_quote_turnover_vs_prior20m":round(turnover15/baseline,3) if baseline else None,
            "max_favorable_excursion_pct":round(favorable,4),
            "max_adverse_excursion_pct":round(adverse,4),
            "definition":"1m close breaks previous 60m high/low; no 1m close returns inside that level for 120 full minutes"
        })
        last_start=i
    return events


async def run():
    OUT.mkdir(parents=True,exist_ok=True)
    end_ms=(int(datetime.now(timezone.utc).timestamp()*1000)//60000)*60000
    start_ms=end_ms-24*60*60000
    mid_ms=start_ms+12*60*60000
    timeout=aiohttp.ClientTimeout(total=40,connect=12)
    headers={"User-Agent":"Bitget-2h-Trend-Research/1.0"}
    async with aiohttp.ClientSession(timeout=timeout,headers=headers) as s:
        instruments,tickers=await asyncio.gather(
            get(s,"/api/v3/market/instruments",{"category":CATEGORY}),
            get(s,"/api/v3/market/tickers",{"category":CATEGORY}))
        live={x.get("symbol") for x in instruments if x.get("status")=="online"
              and (x.get("type")=="perpetual" or x.get("instrumentType")=="perpetual")
              and x.get("symbolType","crypto")=="crypto"}
        universe=sorted([x for x in tickers if x.get("symbol") in live],
                        key=lambda x:num(x.get("turnover24h")),reverse=True)[:LIMIT]
        sem=asyncio.Semaphore(CONCURRENCY)
        errors=[]
        async def one(t):
            symbol=t["symbol"]
            async with sem:
                try:
                    async def page(a,b):
                        return await get(s,"/api/v3/market/candles",{
                            "category":CATEGORY,"symbol":symbol,"interval":"1m",
                            "startTime":str(a),"endTime":str(b),"limit":"1000"})
                    a,b=await asyncio.gather(page(start_ms,mid_ms),page(mid_ms,end_ms))
                    rows=normalize(a+b)
                    if len(rows)<120:
                        raise RuntimeError(f"only {len(rows)} candles returned")
                    return symbol,num(t.get("turnover24h")),rows,None
                except Exception as e:
                    return symbol,num(t.get("turnover24h")),[],str(e)[:250]
        fetched=await asyncio.gather(*(one(t) for t in universe))
    all_events=[]
    coverage=[]
    for symbol,turnover,rows,error in fetched:
        if error: errors.append({"symbol":symbol,"error":error})
        ev=backtest(symbol,rows,start_ms,end_ms) if rows else []
        all_events.extend(ev)
        coverage.append({"symbol":symbol,"turnover24h_usdt":turnover,
                         "closed_1m_candles":len(rows),"qualifying_2h_trends":len(ev),
                         "long_trends":sum(x["direction"]=="LONG" for x in ev),
                         "short_trends":sum(x["direction"]=="SHORT" for x in ev),
                         "error":error})
    by_symbol=[]
    for c in coverage:
        ev=[x for x in all_events if x["symbol"]==c["symbol"]]
        c["positive_120m_follow_through"]=sum(x["direction_adjusted_120m_return_pct"]>0 for x in ev)
        c["avg_120m_direction_adjusted_return_pct"]=round(sum(x["direction_adjusted_120m_return_pct"] for x in ev)/len(ev),4) if ev else None
        c["avg_first15m_direction_matching_pct"]=round(sum(x["direction_matching_pct_first15m"] for x in ev)/len(ev),2) if ev else None
        by_symbol.append(c)
    successful=[x for x in coverage if not x["error"]]
    returns=[x["direction_adjusted_120m_return_pct"] for x in all_events]
    lines=[
      "# Bitget 24-hour 1-minute backtest: trends lasting 2+ hours","",
      f"- Run time UTC: {datetime.now(timezone.utc).isoformat()}",
      f"- Window UTC: {datetime.fromtimestamp(start_ms/1000,timezone.utc).isoformat()} to {datetime.fromtimestamp(end_ms/1000,timezone.utc).isoformat()}",
      f"- Universe: top {len(universe)} online crypto USDT perpetuals by Bitget 24h turnover",
      f"- Candle interval: 1 minute; incomplete candle excluded",
      f"- Coverage: {len(successful)}/{len(universe)} symbols fetched successfully; {sum(x['closed_1m_candles'] for x in coverage):,} closed candles",
      f"- Qualifying sustained trends: {len(all_events)} (LONG {sum(x['direction']=='LONG' for x in all_events)}, SHORT {sum(x['direction']=='SHORT' for x in all_events)})",
      f"- Fetch errors: {len(errors)}",
      "",
      "## How a 2-hour trend is defined",
      "A start is a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). It qualifies only if every subsequent closed 1m candle for 120 minutes remains outside that broken level. This deliberately strict rule avoids calling a brief spike a 2-hour trend. It is a reproducible breakout/hold proxy, not a universal definition of trend.",
      "",
      "## Aggregate findings",
      f"- Positive direction-adjusted return at 120m: {sum(x>0 for x in returns)}/{len(returns)} ({(sum(x>0 for x in returns)/len(returns)*100):.1f}%)" if returns else "- No qualifying 2-hour trends found.",
      f"- Mean direction-adjusted 120m return: {sum(returns)/len(returns):.4f}%" if returns else "",
      f"- Median direction-adjusted 120m return: {sorted(returns)[len(returns)//2]:.4f}%" if returns else "",
      f"- Mean matching candle share in first 15m: {sum(x['direction_matching_pct_first15m'] for x in all_events)/len(all_events):.1f}%" if all_events else "",
      f"- Mean matching candle share over 120m: {sum(x['direction_matching_pct_120m'] for x in all_events)/len(all_events):.1f}%" if all_events else "",
      "",
      "## Per-coin coverage and results",
      "| Symbol | 1m candles | 2h trends | LONG | SHORT | Positive 120m | Avg 120m return % | First 15m matching % | Status |",
      "|---|---:|---:|---:|---:|---:|---:|---:|---|"
    ]
    for c in sorted(by_symbol,key=lambda x:(x["qualifying_2h_trends"],x["turnover24h_usdt"]),reverse=True):
        lines.append(f"| {c['symbol']} | {c['closed_1m_candles']} | {c['qualifying_2h_trends']} | {c['long_trends']} | {c['short_trends']} | {c['positive_120m_follow_through']} | {c['avg_120m_direction_adjusted_return_pct']} | {c['avg_first15m_direction_matching_pct']} | {'ERROR: '+c['error'] if c['error'] else 'OK'} |")
    lines += ["","## Every qualifying trend event",
      "| Symbol | Direction | Start UTC | 120m return % | Matching candles 15m | Matching candles 120m | Volume x | Max favorable % | Max adverse % |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for e in sorted(all_events,key=lambda x:x["direction_adjusted_120m_return_pct"],reverse=True):
        lines.append(f"| {e['symbol']} | {e['direction']} | {e['start_utc']} | {e['direction_adjusted_120m_return_pct']} | {e['direction_matching_candles_first15m']}/15 | {e['direction_matching_candles_120m']}/120 | {e['first15m_quote_turnover_vs_prior20m']} | {e['max_favorable_excursion_pct']} | {e['max_adverse_excursion_pct']} |")
    lines += ["","## Data quality and caveats",
      "- Public Bitget candle data only; no private account access and no orders.",
      "- The requested 24h window is freshly fetched for this run; it does not depend on how long the existing scanner session has been collecting.",
      "- The top 200 universe is selected at run time by reported 24h turnover, so it is a defined and reproducible liquid-activity sample, not every listed contract.",
      "- A strict 60m breakout plus 120m hold rule can miss trends that start without a range breakout, or trends that briefly retest the breakout level.",
      "- Returns are raw direction-adjusted price changes, before fees, spread, slippage and funding. They are not a profitable strategy claim.",
      "- First 15m candle alignment is descriptive only; it must be compared with continuation and adverse excursion, not used alone.",
      ""]
    report="\n".join(x for x in lines if x is not None)+"\n"
    (OUT/"bitget_24h_2h_trend_backtest.md").write_text(report,encoding="utf-8")
    (OUT/"bitget_24h_2h_trend_events.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in all_events),encoding="utf-8")
    (OUT/"bitget_24h_2h_trend_coin_summary.json").write_text(json.dumps({
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),"window_start_ms":start_ms,
      "window_end_ms":end_ms,"symbols_requested":len(universe),"symbols_successful":len(successful),
      "symbols_failed":len(errors),"events":len(all_events),"coverage":coverage,"errors":errors
    },indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"report":"reports/daily_research/bitget_24h_2h_trend_backtest.md",
      "symbols_requested":len(universe),"symbols_successful":len(successful),
      "symbols_failed":len(errors),"closed_1m_candles":sum(x["closed_1m_candles"] for x in coverage),
      "qualifying_2h_trends":len(all_events),"long":sum(x["direction"]=="LONG" for x in all_events),
      "short":sum(x["direction"]=="SHORT" for x in all_events)},indent=2))


if __name__=="__main__":
    asyncio.run(run())
