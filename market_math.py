# market_math.py

class MarketMath:
    @staticmethod
    def audit_precision_8pct_setup(candles: list) -> dict:
        """
        Your Exact Setup:
        1. MACRO: Move >= 8.0% in < 4 hours (between 15 and 240 mins).
        2. TIGHT ABSORPTION: Distance from peak/trough <= 1.60%.
        3. 10-CANDLE WIN STREAK: Last 10 1m candles have >= 8 wins, <= 2 losses.
        4. ACTIVE FLUCTUATION: Average 1m candle amplitude (high-low) >= 0.20%.
        """
        if not isinstance(candles, list) or len(candles) < 25:
            return {"qualified": False}

        try:
            # Handles both Bitget [ts, o, h, l, c, ...] and Binance formats
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]
            curr_price = float(candles[-1][4])

            max_p = max(highs)
            min_p = min(lows)
            peak_idx = highs.index(max_p)
            trough_idx = lows.index(min_p)

            # Inspect the last 10 completed 1-minute candles
            last_10 = candles[-10:]
            candle_amplitudes = []
            green_count = 0
            red_count = 0

            for c in last_10:
                o, h, l, cl = float(c[1]), float(c[2]), float(c[3]), float(c[4])
                # True candle fluctuation range (High - Low)
                amp = ((h - l) / l) * 100.0 if l > 0 else 0.0
                candle_amplitudes.append(amp)

                if cl >= o:
                    green_count += 1
                else:
                    red_count += 1

            avg_fluctuation = sum(candle_amplitudes) / len(candle_amplitudes)

            # Rule 4: Average 1m candle fluctuation must be >= 0.20%
            if avg_fluctuation < 0.20:
                return {"qualified": False}

            # ----------------- 1. EVALUATE LONG -----------------
            if peak_idx > 5:
                # Scan backwards up to 90 mins to find true impulse origin
                lookback_start = max(0, peak_idx - 90)
                sub_lows = lows[lookback_start:peak_idx]
                start_low = min(sub_lows)
                start_idx = lookback_start + sub_lows.index(start_low)
                duration = max(1, peak_idx - start_idx)

                # Rule 1: Move >= 8.0% in < 4 hours (15m to 240m)
                if 10 <= duration <= 240:
                    up_move = ((max_p - start_low) / start_low) * 100.0
                    if up_move >= 8.0:
                        # Rule 2: Reversal from peak <= 1.6%
                        dist_from_peak = ((max_p - curr_price) / max_p) * 100.0
                        if dist_from_peak <= 1.60:
                            # Rule 3: Last 10m has >= 8 green, <= 2 red
                            if green_count >= 8 and red_count <= 2:
                                velocity = up_move / duration
                                return {
                                    "qualified": True,
                                    "direction": "buy",
                                    "total_wave": round(up_move, 2),
                                    "duration_mins": duration,
                                    "dist_from_peak": round(dist_from_peak, 2),
                                    "green_wins": green_count,
                                    "red_losses": red_count,
                                    "avg_fluctuation": round(avg_fluctuation, 3),
                                    "velocity": round(velocity, 3),
                                    "power_score": round(velocity * avg_fluctuation * 100, 2)
                                }

            # ----------------- 2. EVALUATE SHORT -----------------
            if trough_idx > 5:
                lookback_start = max(0, trough_idx - 90)
                sub_highs = highs[lookback_start:trough_idx]
                start_high = max(sub_highs)
                start_idx = lookback_start + sub_highs.index(start_high)
                duration = max(1, trough_idx - start_idx)

                if 10 <= duration <= 240:
                    down_move = ((start_high - min_p) / start_high) * 100.0
                    if down_move >= 8.0:
                        dist_from_trough = ((curr_price - min_p) / min_p) * 100.0
                        if dist_from_trough <= 1.60:
                            if red_count >= 8 and green_count <= 2:
                                velocity = down_move / duration
                                return {
                                    "qualified": True,
                                    "direction": "sell",
                                    "total_wave": round(down_move, 2),
                                    "duration_mins": duration,
                                    "dist_from_peak": round(dist_from_trough, 2),
                                    "green_wins": red_count,
                                    "red_losses": green_count,
                                    "avg_fluctuation": round(avg_fluctuation, 3),
                                    "velocity": round(velocity, 3),
                                    "power_score": round(velocity * avg_fluctuation * 100, 2)
                                }

            return {"qualified": False}
        except Exception:
            return {"qualified": False}

    @staticmethod
    def audit_wiggle_direction(price_ticks: list, direction: str) -> dict:
        """Zero-latency structural momentum exhaustion detection."""
        if len(price_ticks) < 4:
            return {"should_exit": False, "status": "STABLE"}

        p1, p2, p3, p4 = price_ticks[-4], price_ticks[-3], price_ticks[-2], price_ticks[-1]

        if direction == "buy":
            wiggling_down = (p4 < p2 and p3 < p1) or (p4 < p3 < p2)
            return {"should_exit": wiggling_down, "status": "WIGGLING_DOWN" if wiggling_down else "RIDING_UP"}
        else:
            wiggling_up = (p4 > p2 and p3 > p1) or (p4 > p3 > p2)
            return {"should_exit": wiggling_up, "status": "WIGGLING_UP" if wiggling_up else "DUMPING_DOWN"}
