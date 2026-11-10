from collections import deque

class MicroMomentumStrategy:
    def __init__(self, ai_selected_coin, dynamic_trigger):
        self.name = f"4H Adaptive Momentum on {ai_selected_coin}"
        self.prices = deque(maxlen=15)
        self.in_position = False
        self.peak_price = 0
        self.entry_price = 0
        # The trigger is calculated from the last 4 hours!
        self.dynamic_trigger = dynamic_trigger 

    def analyze(self, current_price):
        self.prices.append(current_price)
        
        if len(self.prices) < 10:
            return "HOLD", 0.0

        # 1. ENTRY LOGIC: Breakout of the micro-range based on 4H behavior
        if not self.in_position:
            recent_high = max(list(self.prices)[:-1]) 
            
            # If price breaks the micro-high by the dynamic trigger
            if current_price > recent_high * (1 + self.dynamic_trigger): 
                self.in_position = True
                self.peak_price = current_price
                self.entry_price = current_price
                return "BUY", 0.0
            return "HOLD", 0.0

        # 2. EXIT LOGIC (Trailing micro-trend, no fixed TP/SL)
        if self.in_position:
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            micro_trend = min(list(self.prices)[-3:])
            gross_pnl = (current_price - self.entry_price) / self.entry_price

            if current_price < micro_trend:
                self.in_position = False
                return "SELL_MOMENTUM_DIED", gross_pnl

            if current_price < self.peak_price * 0.995:
                self.in_position = False
                return "SELL_TRAILING_STOP", gross_pnl

        return "HOLD", 0.0
