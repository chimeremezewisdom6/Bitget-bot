from pathlib import Path
import unittest

class ShadowOnlyBoundaryTests(unittest.TestCase):
    def test_research_modules_contain_no_order_or_account_routes(self):
        root = Path(__file__).resolve().parents[1]
        modules = ["daily_research.py", "shadow_research.py", "shadow_execution.py", "research_report.py"]
        forbidden = ["/api/v3/order", "/api/v3/account", "/api/v3/position", "/api/v3/set-leverage", "/api/v3/trade"]
        for name in modules:
            source = (root / name).read_text(encoding="utf-8").lower()
            for route in forbidden:
                self.assertNotIn(route, source, f"{name} contains forbidden route {route}")
            self.assertNotIn(".post(", source, f"{name} must use read-only HTTP methods")

if __name__ == "__main__":
    unittest.main()
