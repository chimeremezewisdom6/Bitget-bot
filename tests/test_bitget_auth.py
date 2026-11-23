import os
import unittest
from unittest.mock import patch

from daily_research import auth_headers, credentials, make_signature


class BitgetAuthenticationTests(unittest.TestCase):
    def test_signature_is_deterministic_and_query_sensitive(self):
        first = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        same = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        changed = make_signature("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=SPOT")
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)

    def test_credentials_accept_common_passphrase_and_password_aliases(self):
        cases = [
            {"BITGET_API_PASSPHRASE": "canonical"},
            {"BITGET_PASSPHRASE": "short-name"},
            {"BITGET_API_PASSWORD": "api-password"},
            {"BITGET_PASSWORD": "password"},
        ]
        for env in cases:
            with self.subTest(env=list(env)):
                full_env = {
                    "BITGET_API_KEY": "test-key",
                    "BITGET_API_SECRET": "test-secret",
                    **env,
                }
                with patch.dict(os.environ, full_env, clear=True):
                    self.assertEqual(credentials(), ("test-key", "test-secret", next(iter(env.values()))))

    def test_credentials_accept_common_secret_aliases(self):
        with patch.dict(os.environ, {
            "BITGET_KEY": "alias-key",
            "BITGET_SECRET": "alias-secret",
            "BITGET_PASSPHRASE": "alias-passphrase",
        }, clear=True):
            self.assertEqual(credentials(), ("alias-key", "alias-secret", "alias-passphrase"))

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
