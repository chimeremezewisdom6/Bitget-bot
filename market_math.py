# market_math.py

class MarketMath:
    @staticmethod
    def audit_15m_breakout(curr_price: float, high_30m: float, vol_24h: float) -> bool:
        """Confirms the coin is breaking out of a 30m resistance ceiling with >= $1M 24h volume."""
        if vol_24h < 1_000_000.0 or high_30m <= 0:
            return False
        return curr_price >= (high_30m * 0.998)

    @staticmethod
    def calculate_5m_fuel(candles) -> dict:
        """
        Measures net aggressive market buy dollars (Taker Buy) over the last 5 minutes.
        Safely validates that Binance returned a valid list of candles.
        """
        if not isinstance(candles, list) or len(candles) < 5:
            return {"has_fuel": False, "net_inflow_5m": 0.0}

        net_inflows = []
        try:
            for c in candles[-5:]:
                if not isinstance(c, (list, tuple)) or len(c) < 11:
                    continue
                q_vol = float(c[7])
                taker_buy = float(c[10])
                taker_sell = max(0.0, q_vol - taker_buy)
                net_inflows.append(taker_buy - taker_sell)
        except Exception:
            return {"has_fuel": False, "net_inflow_5m": 0.0}

        if len(net_inflows) < 5:
            return {"has_fuel": False, "net_inflow_5m": 0.0}

        total_net_inflow = sum(net_inflows)
        # Requires at least $60,000 in net aggressive buying power over 5m
        has_fuel = (total_net_inflow >= 60_000.0) and (net_inflows[-1] > 0)

        return {
            "has_fuel": has_fuel,
            "net_inflow_5m": total_net_inflow
        }

    @staticmethod
    def audit_runway_clearance(orderbooks: list, net_inflow_5m: float) -> dict:
        """
        Sums resting sell orders across all reporting platforms strictly inside
        the +1.50% target runway.
        Safely handles 2-item, 3-item, or 4-item order book rows (like OKX).
        """
        total_ask_wall_usd = 0.0
        venues_reporting = 0

        for name, bids, asks in orderbooks:
            if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
                continue

            try:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid = (best_bid + best_ask) / 2.0
                target_ceiling = mid * 1.015  # +1.50% Target Zone

                # Safe access: index [0] = price, index [1] = size
                valid_asks = [
                    float(item[0]) * float(item[1])
                    for item in asks
                    if len(item) >= 2 and float(item[0]) <= target_ceiling
                ]
                total_ask_wall_usd += sum(valid_asks)
                venues_reporting += 1
            except Exception:
                continue

        # Clearance ratio: Can the 5m buyer inflow clear the entire resting sell wall?
        clearance_ratio = net_inflow_5m / max(total_ask_wall_usd, 1.0)
        has_runway = (clearance_ratio >= 1.30) and (venues_reporting >= 2)

        return {
            "has_runway": has_runway,
            "clearance_ratio": round(clearance_ratio, 2),
            "wall_usd": round(total_ask_wall_usd, 2),
            "venues_count": venues_reporting
        }
