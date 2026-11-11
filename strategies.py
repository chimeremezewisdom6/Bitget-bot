import time
from collections import deque

class ReversalStrategy:
    def __init__(self, coin):
        self.coin = coin
        # Keep 4 hours of data (240 minutes)
        self.history = deque(maxlen=240) 
        self.position = None # None, 'LONG', or 'SHORT'
        self.entry_price = 0
        self.peak_price = 0
        self.trough_price = 0

    def analyze(self, current_price):
        now = time.time()
        self.history.append((now, current_price))
        
        # We need at least 4 hours of data to know its true baseline behavior
        if len(self.history) < 240:
            return "HOLD", 0.0

        if self.position is None:
            # 1. The Baseline (First 3 hours)
            baseline = list(self.history)[:180]
            b_high = max(p for t, p in baseline)
            b_low = min(p for t, p in baseline)
            
            # Check if it was stable (Ranging less than 4%)
            b_range_pct = (b_high - b_low) / b_low
            
            if b_range_pct < 0.04: # It was stable!
                # 2. The Stretch (Last 1 hour)
                recent = list(self.history)[180:]
                
                # --- DROP & REBOUND (LONG) ---
                s_low = min(p for t, p in recent)
                low_time = next(t for t, p in recent if p == s_low)
                
                # Was it a violent drop from the baseline?
                if s_low < b_low * 0.95: # Dropped at least 5% below baseline
                    stretch_size = b_low - s_low
                    current_rebound = current_price - s_low
                    
                    # How much of the stretch has it recovered? (Want 15% to 25%)
                    rebound_ratio = current_rebound / stretch_size if stretch_size > 0 else 0
                    time_since_low = (now - low_time) / 60.0 # in minutes
                    
                    # Must take 10+ mins to develop, and retrace ~20%
                    if time_since_low >= 10.0 and 0.15 <= rebound_ratio <= 0.25:
                        self.position = 'LONG'
                        self.entry_price = current_price
                        self.peak_price = current_price
                        self.trough_price = s_low
                        print(f"🟢 LONG! Stable 4H. Dropped {stretch_size/s_low*100:.1f}%. Rebound: {rebound_ratio*100:.1f}% over {time_since_low:.0f} mins.", flush=True)
                        return "BUY_LONG", 0.0

                # --- PUMP & DROP (SHORT) ---
                s_high = max(p for t, p in recent)
                high_time = next(t for t, p in recent if p == s_high)
                
                if s_high > b_high * 1.05: # Pumped at least 5% above baseline
                    stretch_size = s_high - b_high
                    current_drop = s_high - current_price
                    
                    # How much of the pump has it given back? (Want 15% to 25%)
                    drop_ratio = current_drop / stretch_size if stretch_size > 0 else 0
                    time_since_high = (now - high_time) / 60.0 # in minutes
                    
                    if time_since_high >= 10.0 and 0.15 <= drop_ratio <= 0.25:
                        self.position = 'SHORT'
                        self.entry_price = current_price
                        self.peak_price = s_high
                        self.trough_price = current_price
                        print(f"🔴 SHORT! Stable 4H. Pumped {stretch_size/s_high*100:.1f}%. Drop: {drop_ratio*100:.1f}% over {time_since_high:.0f} mins.", flush=True)
                        return "SELL_SHORT", 0.0

        # --- EXIT LOGIC ---
        if self.position == 'LONG':
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            gross_pnl = (current_price - self.entry_price) / self.entry_price
            avg_price = sum(p for t, p in self.history) / len(self.history)
            
            if current_price >= avg_price:
                self.position = None
                return "CLOSE_LONG", gross_pnl
            if current_price < self.peak_price * 0.99:
                self.position = None
                return "CLOSE_LONG", gross_pnl
            if gross_pnl <= -0.025:
                self.position = None
                return "CLOSE_LONG", gross_pnl

        elif self.position == 'SHORT':
            if current_price < self.trough_price:
                self.trough_price = current_price
                
            gross_pnl = (self.entry_price - current_price) / self.entry_price
            avg_price = sum(p for t, p in self.history) / len(self.history)
            
            if current_price <= avg_price:
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            if current_price > self.trough_price * 1.01:
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            if gross_pnl <= -0.025:
                self.position = None
                return "CLOSE_SHORT", gross_pnl

        return "HOLD", 0.0
