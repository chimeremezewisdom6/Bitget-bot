# market_math.py

class MarketMath:
    @staticmethod
    def audit_reversal_candidate(candles: list, current_price: float) -> dict:
        """
        1. 1-Hour Health Check: Must average >= 0.10%/min fluctuation over the last 60m.
        2. Outlier Move: >= 4.5% to 14.0% in <= 40 minutes.
        3. Fresh 1% Rebound: Rebounded 0.80% to 1.75% off the extreme floor/ceiling.
        4. Turn Candle: Rebound candle must close in the direction of the trade.
        """
        if not isinstance(candles, list) or len(candles) < 60:
            return {"qualified": False}

        try:
            # 1. 1-Hour Volatility Baseline
            last_60 = candles[-60:]
            fluctuations_1h = [
                ((float(c[2]) - float(c[3])) / float(c[3])) * 100.0
                for c in last_60 if float(c[3]) > 0
            ]
            avg_1h_fluctuation = sum(fluctuations_1h) / len(fluctuations_1h) if fluctuations_1h else 0.0

            if avg_1h_fluctuation < 0.10:
                return {"qualified": False}

            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]

            max_p = max(highs)
            min_p = min(lows)
            peak_idx = highs.index(max_p)
            trough_idx = lows.index(min_p)

            latest_candle = candles[-1]
            c_open = float(latest_candle[1])
            c_close = float(latest_candle[4])

            # ----------------- 1. DUMP TO LONG SNAPBACK -----------------
            if trough_idx < len(candles) - 1:
                lookback_start = max(0, trough_idx - 50)
                start_high = max(highs[lookback_start:trough_idx + 1])
                dump_move = ((start_high - min_p) / start_high) * 100.0

                if 4.5 <= dump_move <= 14.0:
                    bounce_from_low = ((current_price - min_p) / min_p) * 100.0

                    # 1% Rebound Confirmation Zone (0.80% to 1.75%)
                    if 0.80 <= bounce_from_low <= 1.75:
                        if c_close >= c_open:
                            return {
                                "qualified": True,
                                "direction": "buy",
                                "extreme_move": round(dump_move, 2),
                                "rebound_pct": round(bounce_from_low, 2),
                                "avg_1h_fluctuation": round(avg_1h_fluctuation, 3)
                            }

            # ----------------- 2. PUMP TO SHORT ROLLOVER -----------------
            if peak_idx < len(candles) - 1:
                lookback_start = max(0, peak_idx - 50)
                start_low = min(lows[lookback_start:peak_idx + 1])
                pump_move = ((max_p - start_low) / start_low) * 100.0

                if 4.5 <= pump_move <= 14.0:
                    drop_from_high = ((max_p - current_price) / max_p) * 100.0

                    # 1% Rollover Confirmation Zone (0.80% to 1.75%)
                    if 0.80 <= drop_from_high <= 1.75:
                        if c_close <= c_open:
                            return {
                                "qualified": True,
                                "direction": "sell",
                                "extreme_move": round(pump_move, 2),
                                "rebound_pct": round(drop_from_high, 2),
                                "avg_1h_fluctuation": round(avg_1h_fluctuation, 3)
                            }

            return {"qualified": False}
        except Exception:
            return {"qualified": False}

    @staticmethod
    def audit_cross_imbalance(orderbooks: list, direction: str) -> dict:
        """Calculates Global Order Book Imbalance across all 8 reporting exchanges."""
        total_bid_usd = 0.0
        total_ask_usd = 0.0
        venues_reporting = 0

        for name, bids, asks in orderbooks:
            if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
                continue

            try:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid = (best_bid + best_ask) / 2.0
                upper_bound = mid * 1.012  # +1.2% Target Zone
                lower_bound = mid * 0.988  # -1.2% Support Floor

                valid_asks = [
                    float(item[0]) * float(item[1])
                    for item in asks
                    if len(item) >= 2 and float(item[0]) <= upper_bound
                ]
                valid_bids = [
                    float(item[0]) * float(item[1])
                    for item in bids
                    if len(item) >= 2 and float(item[0]) >= lower_bound
                ]

                total_ask_usd += sum(valid_asks)
                total_bid_usd += sum(valid_bids)
                venues_reporting += 1
            except Exception:
                continue

        if venues_reporting < 2:
            return {"has_imbalance": False, "imbalance_ratio": 0.0, "venues_count": 0}

        if direction == "buy":
            imbalance_ratio = total_bid_usd / max(total_ask_usd, 1.0)
        else:
            imbalance_ratio = total_ask_usd / max(total_bid_usd, 1.0)

        # Minimum 1.40x imbalance across exchanges
        has_imbalance = imbalance_ratio >= 1.40

        return {
            "has_imbalance": has_imbalance,
            "imbalance_ratio": round(imbalance_ratio, 2),
            "total_bid_usd": round(total_bid_usd, 2),
            "total_ask_usd": round(total_ask_usd, 2),
            "venues_count": venues_reporting
        }

    @staticmethod
    def audit_wave_exhaustion(price_ticks: list, direction: str) -> bool:
        """
        Structural wave check over ~35 seconds (avoids getting shaken out by 4s micro-noise).
        """
        if len(price_ticks) < 8:
            return False

        # Look at 8 ticks (~32 seconds of market structure)
        recent_half = price_ticks[-4:]
        prior_half = price_ticks[-8:-4]

        avg_recent = sum(recent_half) / 4.0
        avg_prior = sum(prior_half) / 4.0

        if direction == "buy":
            # Wave structure breaking downward
            return avg_recent < avg_prior and price_ticks[-1] < min(recent_half[:-1])
        else:
            # Wave structure breaking upward
            return avg_recent > avg_prior and price_ticks[-1] > max(recent_half[:-1])
