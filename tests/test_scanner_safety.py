import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import scanner


class ScannerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.rules = {
            "symbol": "TESTUSDT",
            "status": "online",
            "quantityPrecision": "3",
            "quantityMultiplier": "0.001",
            "minOrderQty": "0.001",
            "minOrderAmount": "5.01",
            "maxOrderQty": "0",
            "maxLeverage": "3",
            "pricePrecision": "2",
            "priceMultiplier": "0.01",
        }

    def test_api_key_selection_is_stable_and_does_not_rotate_accounts(self):
        keys = [
            {"key": "demo-account-a", "secret": "a", "passphrase": "a", "id": 1},
            {"key": "demo-account-b", "secret": "b", "passphrase": "b", "id": 2},
        ]
        with patch.object(scanner, "BITGET_KEYS", keys):
            first = scanner.get_next_bitget_key()
            second = scanner.get_next_bitget_key()
            third = scanner.get_next_bitget_key()

        self.assertIs(first, keys[0])
        self.assertIs(second, first)
        self.assertIs(third, first)

    def test_strategy_is_demo_only_and_thresholds_match(self):
        self.assertIs(scanner.BITGET_DEMO_MODE, True)
        self.assertEqual(scanner.MIN_24H_VOLUME, 500000)
        self.assertEqual(scanner.MIN_REQUIRED_COLOR_COUNT, 42)
        self.assertEqual(scanner.TARGET_COLOR_COUNT, 30)
        self.assertEqual(scanner.MAX_TRADE_DURATION_MIN, 54.0)
        self.assertEqual(scanner.DEFAULT_LEVERAGE, 5)

    def test_quantity_obeys_exchange_step_and_minimum_notional(self):
        result = scanner.calculate_ai_position_parameters(
            2.0, 100.0, 1.0, 90.0, self.rules
        )
        self.assertIsNotNone(result)
        margin, qty, notional, leverage = result
        self.assertAlmostEqual(qty / 0.001, round(qty / 0.001))
        self.assertGreaterEqual(notional, 5.01)
        self.assertEqual(leverage, 3)
        self.assertAlmostEqual(margin, notional / leverage)

    def test_contract_max_leverage_is_never_exceeded(self):
        rules = dict(self.rules, maxLeverage="1")
        result = scanner.calculate_ai_position_parameters(
            2.0, 100.0, 1.0, 99.0, rules
        )
        self.assertEqual(result[3], 1)

    def test_invalid_contract_rules_fail_closed(self):
        rules = dict(self.rules, quantityMultiplier="0")
        self.assertIsNone(
            scanner.calculate_ai_position_parameters(
                2.0, 100.0, 1.0, 90.0, rules
            )
        )

    def test_candle_selection_uses_latest_completed_candles_in_order(self):
        minute_ms = 60_000
        now_ms = 100 * minute_ms + 30_000
        candles = [
            [str(i * minute_ms), "1", "2", "0.5", str(i), "1", "1"]
            for i in range(100)
        ]
        selected = scanner.select_latest_completed_candles(
            candles, now_ms=now_ms, count=60
        )

        self.assertEqual(len(selected), 60)
        timestamps = [int(candle[0]) for candle in selected]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(timestamps[0], 39 * minute_ms)
        self.assertEqual(timestamps[-1], 98 * minute_ms)

    def test_incomplete_candle_is_excluded(self):
        minute_ms = 60_000
        now_ms = 100 * minute_ms + 30_000
        candles = [
            [str(i * minute_ms), "1", "2", "0.5", "1.5", "1", "1"]
            for i in range(60)
        ]
        selected = scanner.select_latest_completed_candles(
            candles, now_ms=now_ms, count=60
        )
        self.assertEqual(len(selected), 60)
        self.assertTrue(all(int(c[0]) + minute_ms <= now_ms for c in selected))

    def test_stop_price_rounds_outward_to_exchange_tick(self):
        self.assertEqual(
            scanner.format_instrument_price(1.234, self.rules, "LONG"), "1.23"
        )
        self.assertEqual(
            scanner.format_instrument_price(1.234, self.rules, "SHORT"), "1.24"
        )

    def test_dry_run_never_attempts_to_change_leverage(self):
        async def run_dry_order():
            with patch.object(scanner, "DRY_RUN", True), \
                 patch.object(scanner, "fetch_contract_rules", new_callable=AsyncMock) as rules_mock, \
                 patch.object(scanner, "configure_bitget_leverage", new_callable=AsyncMock) as leverage_mock:
                rules_mock.return_value = self.rules
                result = await scanner.place_bitget_live_order(
                    session=None,
                    symbol="TESTUSDT",
                    direction="LONG",
                    market_price=2.0,
                    available_balance=100.0,
                    dynamic_sl=1.90,
                )
                self.assertIsNone(result)
                leverage_mock.assert_not_awaited()

        asyncio.run(run_dry_order())


if __name__ == "__main__":
    unittest.main()
