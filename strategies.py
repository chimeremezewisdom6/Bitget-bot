import time
from collections import deque

class GradualReversalStrategy:
    def __init__(self, coin):
        self.coin = coin
        # We track the last 60 minutes of (timestamp, price)
        self.history = deque(maxlen=60) 
        self.in_position = False
        self.entry_price = 0
        self.peak_price = 0

    def analyze(self, current_price):
        now = time.time()
        self.history.append((now, current_price))
        
        # Need at least 30 minutes of data to judge the speed of the drop
        if len(self.history) < 30:
            return "HOLD", 0.0

        # --- ENTRY LOGIC ---
        if not self.in_position:
            # 1. Find the lowest price (the bottom)
            low_idx = min(range(len(self.history)), key=lambda i: self.history[i][1])
            recent_low = self.history[low_idx][1]
            low_time = self.history[low_idx][0]
            
            # If the lowest price just happened right now, we don't have a bounce yet
            if low_idx >= len(self.history) - 1:
                return "HOLD", 0.0

            # 2. Find the highest price BEFORE the low (the peak of the drop)
            pre_drop_history = self.history[:low_idx]
            if not pre_drop_history:
                return "HOLD", 0.0
                
            high_idx = max(range(len(pre_drop_history)), key=lambda i: pre_drop_history[i][1])
            recent_high = pre_drop_history[high_idx][1]
            peak_time = pre_drop_history[high_idx][0]
            
            # 3. Calculate Drop Percentage and Duration
            drop_pct = (recent_high - recent_low) / recent_high
            drop_duration_mins = (low_time - peak_time) / 60.0
            
            # 4. Calculate Bounce Percentage
            bounce_pct = (current_price - recent_low) / recent_low

            # --- YOUR STRICT RULES ---
            # 1. Dropped at least 5%
            # 2. Took at least 30 minutes to drop (Slow Bleed, not a Fast Crash)
            # 3. Bounced between 1.0% and 1.6% from the low
            if drop_pct >= 0.05 and drop_duration_mins >= 30.0:
                if 0.010 <= bounce_pct <= 0.016:
                    self.in_position = True
                    self.entry_price = current_price
                    self.peak_price = current_price
                    print(f"🪀 PERFECT ENTRY! Dropped {drop_pct*100:.2f}% over {drop_duration_mins:.0f} mins. Bounce: {bounce_pct*100:.2f}%", flush=True)
                    return "BUY_REVERSION", 0.0
            
            return "HOLD", 0.0

        # --- EXIT LOGIC ---
        if self.in_position:
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            gross_pnl = (current_price - self.entry_price) / self.entry_price
            
            # Calculate the average price (Simple Moving Average of the 60 mins)
            avg_price = sum(p for t, p in self.history) / len(self.history)
            
            # Exit when it returns to the average price (The snap back)
            if current_price >= avg_price:
                self.in_position = False
                return "SELL_TARGET", gross_pnl
            
            # Trailing Stop (If it drops 1% from peak, protect profit)
            if current_price < self.peak_price * 0.99:
                self.in_position = False
                return "SELL_TARGET", gross_pnl

            # Hard Stop (If it drops another 2.5% below entry, the reversal failed)
            if gross_pnl <= -0.025:
                self.in_position = False
                return "SELL_STOP", gross_pnl

        return "HOLD", 0.0
