import unittest
from pathlib import Path


class PhaseASafetyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_no_order_or_account_write_routes(self):
        forbidden = [
            "/api/v3/trade/", "/api/v2/mix/order/", "/api/v3/order/",
            "/api/v3/position/", "/api/v2/mix/position/",
            "/api/v3/account/set-", "/api/v2/mix/account/set-",
            "/api/v3/account/transfer", "/api/v3/account/withdraw",
            "place-order", "cancel-order", "set-leverage",
        ]
        for package in ("collector", "research"):
            for path in (self.root / package).rglob("*.py"):
                source = path.read_text(encoding="utf-8").lower()
                for route in forbidden:
                    self.assertNotIn(route, source, f"{path.name} contains {route}")

    def test_no_write_http_methods(self):
        for package in ("collector", "research"):
            for path in (self.root / package).rglob("*.py"):
                source = path.read_text(encoding="utf-8").lower()
                for method in (".post(", ".put(", ".delete(", ".patch("):
                    self.assertNotIn(method, source, f"{path.name} contains {method}")

    def test_public_client_is_market_only(self):
        from collector.bitget_public import ALLOWED_PREFIXES
        self.assertEqual(ALLOWED_PREFIXES, ("/api/v3/market/",))

    def test_auth_client_has_two_read_only_paths(self):
        from collector.bitget_auth import AUTH_ALLOWED
        self.assertEqual(AUTH_ALLOWED, {"/api/v3/account/info", "/api/v3/account/all-fee-rate"})

    def test_collector_does_not_write_repository_reports(self):
        for path in (self.root / "collector").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("reports/", source, f"{path.name} references reports/")

    def test_pollinations_workflow_is_read_only(self):
        path = self.root / ".github/workflows/verify-pollinations.yml"
        if not path.exists():
            self.skipTest("workflow file is added separately; the current token lacks workflow scope")
        text = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull_request_target", text)


if __name__ == "__main__":
    unittest.main()
