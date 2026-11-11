import math
from collections import deque

class RubberBandStrategy:
    def __init__(self, coin):
        self.coin = coin
        self.prices = deque(maxlen=20)
        self.in_position = False
        self.entry_price = 0
        self.peak_price = 0

    def analyze(self, current_price):
        self.prices.append(current_price)
        if len(self.prices) < 20:
            return "HOLD", 0.0

        # Calculate 20-period Bollinger Bands
        sma = sum(self.prices) / 20
        variance = sum((p - sma) ** 2 for p in self.prices) / 20
        std_dev = math.sqrt(variance)
        
        lower_band = sma - (2.5 * std_dev) # Extreme lower band
        upper_band = sma + (2.5 * std_dev)

        # --- ENTRY LOGIC ---
        if not self.in_position:
            prev_price = self.prices[-2]
            
            # Rubber Band Bounce: Dropped below lower band AND ticked green
            if prev_price <= lower_band and current_price > prev_price:
                self.in_position = True
                self.entry_price = current_price
                self.peak_price = current_price
                return "BUY_REVERSION", 0.0
            return "HOLD", 0.0

        # --- EXIT LOGIC ---
        if self.in_position:
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            gross_pnl = (current_price - self.entry_price) / self.entry_price
            
            # Exit at the middle band (rubber band snapped back to average)
            if current_price >= sma:
                self.in_position = False
                return "SELL_TARGET", gross_pnl
            
            # Trailing Stop (If it drops 1.5% from peak)
            if current_price < self.peak_price * 0.985:
                self.in_position = False
                return "SELL_TARGET", gross_pnl

            # Hard Stop (If the band breaks completely downward)
            if gross_pnl <= -0.025:
                self.in_position = False
                return "SELL_STOP", gross_pnl

        return "HOLD", 0.0
