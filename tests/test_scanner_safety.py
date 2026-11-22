import unittest

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

    def test_stop_price_rounds_outward_to_exchange_tick(self):
        self.assertEqual(
            scanner.format_instrument_price(1.234, self.rules, "LONG"), "1.23"
        )
        self.assertEqual(
            scanner.format_instrument_price(1.234, self.rules, "SHORT"), "1.24"
        )


if __name__ == "__main__":
    unittest.main()
