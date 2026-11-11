class OrderFlowImbalanceStrategy:
    def __init__(self, coin):
        self.coin = coin
        self.position = None  # None, 'LONG', or 'SHORT'
        self.entry_price = 0
        self.peak_price = 0
        self.trough_price = 0

    def analyze(self, bid_ask_ratio, current_price):
        if self.position is None:
            # LONG Trigger: Buyers are 5x stronger
            if bid_ask_ratio >= 5.0:
                self.position = 'LONG'
                self.entry_price = current_price
                self.peak_price = current_price
                return "BUY_LONG", 0.0

            # SHORT Trigger: Sellers are 5x stronger
            if bid_ask_ratio <= 0.20:
                self.position = 'SHORT'
                self.entry_price = current_price
                self.trough_price = current_price
                return "SELL_SHORT", 0.0

        # --- EXIT LOGIC ---
        if self.position == 'LONG':
            if current_price > self.peak_price:
                self.peak_price = current_price
            gross_pnl = (current_price - self.entry_price) / self.entry_price

            # Exit if imbalance disappears (ratio drops below 2x)
            if bid_ask_ratio < 2.0:
                self.position = None
                return "CLOSE_LONG", gross_pnl
            # Trailing stop
            if current_price < self.peak_price * 0.995:
                self.position = None
                return "CLOSE_LONG", gross_pnl
            # Hard stop
            if gross_pnl <= -0.01:
                self.position = None
                return "CLOSE_LONG", gross_pnl

        elif self.position == 'SHORT':
            if current_price < self.trough_price:
                self.trough_price = current_price
            gross_pnl = (self.entry_price - current_price) / self.entry_price

            # Exit if imbalance disappears (ratio rises above 0.5)
            if bid_ask_ratio > 0.5:
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            # Trailing stop
            if current_price > self.trough_price * 1.005:
                self.position = None
                return "CLOSE_SHORT", gross_pnl
            # Hard stop
            if gross_pnl <= -0.01:
                self.position = None
                return "CLOSE_SHORT", gross_pnl

        return "HOLD", 0.0
