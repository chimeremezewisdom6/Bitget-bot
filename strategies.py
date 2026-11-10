from collections import deque

class MicroMomentumStrategy:
    def __init__(self, ai_selected_coin):
        self.name = f"Micro-Momentum on {ai_selected_coin}"
        self.prices = deque(maxlen=15)
        self.in_position = False
        self.peak_price = 0

    def analyze(self, current_price):
        self.prices.append(current_price)
        
        if len(self.prices) < 10:
            return "HOLD"

        # 1. ENTRY LOGIC: Breakout of the micro-range
        if not self.in_position:
            recent_high = max(list(self.prices)[:-1]) 
            
            if current_price > recent_high * 1.001: 
                self.in_position = True
                self.peak_price = current_price
                return "BUY"
            return "HOLD"

        # 2. EXIT LOGIC
        if self.in_position:
            if current_price > self.peak_price:
                self.peak_price = current_price
                
            micro_trend = min(list(self.prices)[-3:])
            
            if current_price < micro_trend:
                self.in_position = False
                return "SELL_MOMENTUM_DIED"

            if current_price < self.peak_price * 0.995:
                self.in_position = False
                return "SELL_TRAILING_STOP"

        return "HOLD"
