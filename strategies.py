import pandas as pd
import ta

class ScalpingStrategy:
    """
    AGGRESSIVE STYLE: Looks at immediate order book pressure and tight spreads.
    """
    def __init__(self):
        self.name = "Aggressive Scalping"

    def analyze(self, orderbook, candles):
        if not orderbook['bids'] or not orderbook['asks'] or len(candles) < 2:
            return "HOLD"

        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        
        spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2
        
        if mid_price == 0:
            return "HOLD"

        # If the spread is extremely tight (< 0.02%), scalp the momentum
        if (spread / mid_price) < 0.0002:
            # Check last candle direction for micro-momentum
            if candles[-1][4] > candles[-1][1]: # Close > Open
                return "BUY"
            else:
                return "SELL"
        return "HOLD"

class TrendFollowingStrategy:
    """
    CONSERVATIVE STYLE: Uses moving averages to ride larger waves.
    Used as a fallback if scalping fails.
    """
    def __init__(self):
        self.name = "Trend Following"

    def analyze(self, orderbook, candles):
        if len(candles) < 25:
            return "HOLD"

        # candles format: [timestamp, open, high, low, close, volume]
        df = pd.DataFrame(candles, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        
        try:
            # Calculate 9 EMA and 21 EMA
            df['ema9'] = ta.trend.ema_indicator(df['close'], window=9)
            df['ema21'] = ta.trend.ema_indicator(df['close'], window=21)
            
            last_close = df['close'].iloc[-1]
            last_ema9 = df['ema9'].iloc[-1]
            last_ema21 = df['ema21'].iloc[-1]

            if pd.isna(last_ema9) or pd.isna(last_ema21):
                return "HOLD"

            # Golden Cross (Bullish)
            if last_ema9 > last_ema21 and last_close > last_ema9:
                return "BUY"
            # Death Cross (Bearish)
            elif last_ema9 < last_ema21 and last_close < last_ema9:
                return "SELL"
        except Exception as e:
            print(f"Trend Analysis Error: {e}")
            
        return "HOLD"
