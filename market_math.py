# market_math.py

class MarketMath:
    @staticmethod
    def audit_wave_dominance(candles: list) -> dict:
        """
        Bi-directional wave analysis:
        - LONG: Move >= +6.5% in <= 45m with shallow pullback <= 22% (10m vs 1.3m rule).
        - SHORT: Dump <= -6.5% in <= 45m with shallow bounce <= 22%.
        - Velocity >= 0.18%/min (Rejects slow multi-hour crawlers).
        """
        if not isinstance(candles, list) or len(candles) < 20:
            return {"qualified": False}

        try:
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]

            max_p = max(highs)
            min_p = min(lows)
            peak_idx = highs.index(max_p)
            trough_idx = lows.index(min_p)

            green_vol = sum(float(c[7]) for c in candles if float(c[4]) >= float(c[1]))
            red_vol = sum(float(c[7]) for c in candles if float(c[4]) < float(c[1]))

            # ----------------- 1. EVALUATE LONG SURGE -----------------
            if peak_idx > 4:
                start_low = min(lows[:peak_idx])
                start_idx = lows.index(start_low)
                duration = max(1, peak_idx - start_idx)

                # Hard time window: between 5 and 45 minutes
                if 5 <= duration <= 45:
                    up_move = ((max_p - start_low) / start_low) * 100.0
                    velocity = up_move / duration

                    if up_move >= 6.5 and velocity >= 0.18:
                        drops = [
                            ((max(highs[:i+1]) - lows[i]) / max(highs[:i+1])) * 100.0
                            for i in range(start_idx + 1, peak_idx)
                        ]
                        max_drop = max(drops) if drops else 0.0
                        reversal_ratio = max_drop / max(up_move, 1.0)

                        if reversal_ratio <= 0.22 and max_drop <= 1.80:
                            fuel_ratio = green_vol / max(red_vol, 1.0)
                            if fuel_ratio >= 1.70:
                                return {
                                    "qualified": True,
                                    "direction": "buy",
                                    "total_wave": round(up_move, 2),
                                    "duration_mins": duration,
                                    "velocity": round(velocity, 3),
                                    "max_reversal": round(max_drop, 2),
                                    "power_score": round(velocity * (1.0 - reversal_ratio) * fuel_ratio, 2)
                                }

            # ----------------- 2. EVALUATE SHORT DUMP -----------------
            if trough_idx > 4:
                start_high = max(highs[:trough_idx])
                start_idx = highs.index(start_high)
                duration = max(1, trough_idx - start_idx)

                if 5 <= duration <= 45:
                    down_move = ((start_high - min_p) / start_high) * 100.0
                    velocity = down_move / duration

                    if down_move >= 6.5 and velocity >= 0.18:
                        bounces = [
                            ((highs[i] - min(lows[:i+1])) / min(lows[:i+1])) * 100.0
                            for i in range(start_idx + 1, trough_idx)
                        ]
                        max_bounce = max(bounces) if bounces else 0.0
                        reversal_ratio = max_bounce / max(down_move, 1.0)

                        if reversal_ratio <= 0.22 and max_bounce <= 1.80:
                            fuel_ratio = red_vol / max(green_vol, 1.0)
                            if fuel_ratio >= 1.70:
                                return {
                                    "qualified": True,
                                    "direction": "sell",
                                    "total_wave": round(down_move, 2),
                                    "duration_mins": duration,
                                    "velocity": round(velocity, 3),
                                    "max_reversal": round(max_bounce, 2),
                                    "power_score": round(velocity * (1.0 - reversal_ratio) * fuel_ratio, 2)
                                }

            return {"qualified": False}
        except Exception:
            return {"qualified": False}

    @staticmethod
    def audit_wiggle_direction(price_ticks: list, direction: str) -> dict:
        """
        Identifies structural momentum exhaustion:
        - For BUY: Exits when lower highs / lower lows form (wiggling down).
        - For SELL: Exits when higher highs / higher lows form (wiggling up).
        """
        if len(price_ticks) < 4:
            return {"should_exit": False, "status": "STABLE"}

        p1, p2, p3, p4 = price_ticks[-4], price_ticks[-3], price_ticks[-2], price_ticks[-1]

        if direction == "buy":
            wiggling_down = (p4 < p2 and p3 < p1) or (p4 < p3 < p2)
            return {"should_exit": wiggling_down, "status": "WIGGLING_DOWN" if wiggling_down else "RIDING_UP"}
        else:
            wiggling_up = (p4 > p2 and p3 > p1) or (p4 > p3 > p2)
            return {"should_exit": wiggling_up, "status": "WIGGLING_UP" if wiggling_up else "DUMPING_DOWN"}
