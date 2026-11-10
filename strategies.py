import pandas as pd
import ta

class ScalpingStrategy:
    def __init__(self):
        self.name = "Aggressive Scalping"

    def analyze(self, orderbook, candles):
        best_bid = orderbook['bids'][0][0] if orderbook['bids'] else 0
        best_ask = orderbook['asks'][0][0] if orderbook['asks'] else 0
        
        if best_bid == 0 or best_ask == 0:
            return "HOLD"

        spread = best_ask - best_bid
        mid_price = (best_ask + best_bid) / 2
        
        if (spread / mid_price) < 0.0002:
            if candles[-1]['close'] > candles[-1]['open']:
                return "BUY"
            else:
                return "SELL"
        return "HOLD"

class TrendFollowingStrategy:
    def __init__(self):
        self.name = "Trend Following"

    def analyze(self, orderbook, candles):
        if len(candles) < 20:
            return "HOLD"

        df = pd.DataFrame(candles)
        df['ema9'] = ta.trend.ema_indicator(df['close'], window=9)
        df['ema21'] = ta.trend.ema_indicator(df['close'], window=21)
        
        last_close = df['close'].iloc[-1]
        last_ema9 = df['ema9'].iloc[-1]
        last_ema21 = df['ema21'].iloc[-1]

        if last_ema9 > last_ema21 and last_close > last_ema9:
            return "BUY"
        elif last_ema9 < last_ema21 and last_close < last_ema9:
            return "SELL"
            
        return "HOLD"
