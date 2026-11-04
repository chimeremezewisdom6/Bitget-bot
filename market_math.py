# market_math.py

class MarketMath:
    @staticmethod
    def audit_15m_breakout(curr_price: float, high_30m: float, vol_24h: float) -> bool:
        """
        Confirms the coin is breaking out of a 30m resistance ceiling with > $1M 24h volume.
        """
        if vol_24h < 1_000_000.0 or high_30m <= 0:
            return False
        # Price must be pushing at or above recent 30m high
        return curr_price >= (high_30m * 0.998)

    @staticmethod
    def calculate_5m_fuel(candles: list) -> dict:
        """
        Measures net aggressive market buy dollars (Taker Buy) over the last 5 minutes.
        """
        if not candles or len(candles) < 5:
            return {"has_fuel": False, "net_inflow_5m": 0.0}

        net_inflows = []
        for c in candles[-5:]:
            q_vol = float(c[7])
            taker_buy = float(c[10])
            taker_sell = max(0.0, q_vol - taker_buy)
            net_inflows.append(taker_buy - taker_sell)

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
        """
        total_ask_wall_usd = 0.0
        venues_reporting = 0

        for name, bids, asks in orderbooks:
            if not bids or not asks:
                continue
            mid = (float(bids[0][0]) + float(asks[0][0])) / 2.0
            target_ceiling = mid * 1.015  # +1.50% Target Zone

            # Sum all resting limit orders up to +1.50%
            valid_asks = [float(p) * float(q) for p, q in asks if float(p) <= target_ceiling]
            total_ask_wall_usd += sum(valid_asks)
            venues_reporting += 1

        # Runway clearance ratio: Can 5m buying force clear the entire +1.5% wall?
        clearance_ratio = net_inflow_5m / max(total_ask_wall_usd, 1.0)
        has_runway = (clearance_ratio >= 1.30) and (venues_reporting >= 2)

        return {
            "has_runway": has_runway,
            "clearance_ratio": round(clearance_ratio, 2),
            "wall_usd": round(total_ask_wall_usd, 2),
            "venues_count": venues_reporting
        }
