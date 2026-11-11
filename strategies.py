import time
from collections import deque

class ReversalStrategy:
    def __init__(self, coin):
        self.coin = coin
        self.history = deque(maxlen=60) # Last 60 minutes
        self.position = None # None, 'LONG', or 'SHORT'
        self.entry_price = 0
        self.peak_price = 0
        self.trough_price = 0

    def analyze(self, current_price):
        now = time.time()
        self.history.append((now, current_price))
        
        if len(self.history) < 30:
            return "HOLD", 0.0

        # --- ENTRY LOGIC ---
        if self.position is None:
            # 1. Find the absolute High and Low in the 60-min window
            high_idx = max(range(len(self.history)), key=lambda i: self.history[i][1])
            low_idx = min(range(len(self.history)), key=lambda i: self.history[i][1])
            
            recent_high = self.history[high_idx][1]
            high_time = self.history[high_idx][0]
            
            recent_low = self.history[low_idx][1]
            low_time = self.history[low_idx][0]

            # 2. Check for LONG (Drop & Bounce)
            # High must happen BEFORE Low
            if high_idx < low_idx:
                drop_pct = (recent_high - recent_low) / recent_high
                duration_mins = (low_time - high_time) / 60.0
                bounce_pct = (current_price - recent_low) / recent_low
                
                if drop_pct >= 0.05 and duration_mins >= 30.0:
                    if 0.010 <= bounce_pct <= 0.016:
                        self.position = 'LONG'
                        self.entry_price = current_price
                        self.trough_price = recent_low
                        self.peak_price = current_price
                        print(f"🟢 LONG SETUP! Dropped {drop_pct*100:.2f}% over {duration_mins:.0f} mins. Bounce: {bounce_pct*100:.2f}%", flush=True)
                        return "BUY_LONG", 0.0

            # 3. Check for SHORT (Pump & Drop)
            # Low must happen BEFORE High
            if low_idx < high_idx:
                pump_pct = (recent_high - recent_low) / recent_low
                duration_mins = (high_time - low_time) / 60.0
                drop_from_peak = (recent_high - current_price) / recent_high
                
                if pump_pct >= 0.05 and duration_mins >= 30.0:
                    if 0.010 <= drop_from_peak <= 0.016:
                        self.position = 'SHORT'
                        self.entry_price = current_price
                        self.peak_price = recent_high
                        self.trough_price = current_price
                        print(f"🔴 SHORT SETUP! Pumped {pump_pct*100:.2f}% over {duration_mins:.0f} mins. Drop from peak: {drop_from_peak*100:.2f}%", flush=True)
                        return "SELL_SHORT", 0.0

            return "HOLD", 0.0

        # --- EXIT LOGIC ---
        if self.position == 'LONG':
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            gross_pnl = (current_price - self.entry_price) / self.entry_price
            avg_price = sum(p for t, p in self.history) / len(self.history)
            
            if current_price >= avg_price:
                self.position = None
                return "CLOSE_LONG", gross_pnl
            if current_price < self.peak_price * 0.99: # 1% trailing stop
                self.position = None
                return "CLOSE_LONG", gross_pnl
            if gross_pnl <= -0.025: # 2.5% hard stop
                self.position = None
                return "CLOSE_LONG", gross_pnl

        elif self.position == 'SHORT':
            if current_price < self.trough_price:
                self.trough_price = current_price
                
            # PnL is inverted for shorts (Entry - Current)
            gross_pnl = (self.entry_price - current_price) / self.entry_price
            avg_price = sum(p for t, p in self.history) / len(self.history)
            
            if current_price <= avg_price:
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            if current_price > self.trough_price * 1.01: # 1% trailing stop
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            if gross_pnl <= -0.025: # 2.5% hard stop
                self.position = None
                return "CLOSE_SHORT", gross_pnl

        return "HOLD", 0.0
