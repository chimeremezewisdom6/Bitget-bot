import json
from pathlib import Path
import unittest


class ShadowOnlyBoundaryTests(unittest.TestCase):
    def test_research_modules_contain_no_order_or_leverage_routes(self):
        root = Path(__file__).resolve().parents[1]
        modules = ["daily_research.py", "cap_watchlist.py", "shadow_execution.py", "research_report.py"]
        forbidden = [
            "/api/v3/trade/", "/api/v2/mix/order/", "/api/v3/order/",
            "/api/v3/position/", "/api/v2/mix/position/",
            "/api/v3/account/set-", "/api/v2/mix/account/set-",
            "/api/v3/account/transfer", "/api/v3/account/withdraw",
        ]
        for name in modules:
            source = (root / name).read_text(encoding="utf-8").lower()
            for route in forbidden:
                self.assertNotIn(route, source, f"{name} contains forbidden route {route}")
            self.assertNotIn(".post(", source, f"{name} must use read-only HTTP methods")

    def test_market_cap_provider_removed_from_runtime_watchlist(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "cap_watchlist.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("coingecko", source)
        self.assertIn("turnover", source)

    def test_authenticated_access_is_limited_to_read_only_fee_metadata(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "daily_research.py").read_text(encoding="utf-8").lower()
        self.assertIn("/api/v3/account/info", source)
        self.assertIn("/api/v3/account/all-fee-rate", source)
        self.assertNotIn("place-order", source)
        self.assertNotIn("cancel-order", source)

    def test_all_config_json_files_are_valid(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "config").glob("*.json"):
            with self.subTest(config=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
