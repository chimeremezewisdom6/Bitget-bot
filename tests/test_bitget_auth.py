import os
import unittest
from unittest.mock import patch

from daily_research import auth_headers, make_signature


class BitgetAuthenticationTests(unittest.TestCase):
    def test_signature_is_deterministic_and_query_sensitive(self):
        first = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        same = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        changed = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=SPOT")
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)

    def test_auth_headers_require_all_three_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                auth_headers("GET", "/api/v3/account/info")

    def test_auth_headers_include_expected_bitget_fields(self):
        env = {
            "BITGET_API_KEY": "test-key",
            "BITGET_API_SECRET": "test-secret",
            "BITGET_API_PASSPHRASE": "test-passphrase",
        }
        with patch.dict(os.environ, env, clear=True):
            headers, query = auth_headers("GET", "/api/v3/account/all-fee-rate", {"category": "USDT-FUTURES"})
        self.assertEqual(query, "category=USDT-FUTURES")
        self.assertEqual(headers["ACCESS-KEY"], "test-key")
        self.assertTrue(headers["ACCESS-SIGN"])
        self.assertTrue(headers["ACCESS-TIMESTAMP"])
        self.assertEqual(headers["ACCESS-PASSPHRASE"], "test-passphrase")


if __name__ == "__main__":
    unittest.main()
