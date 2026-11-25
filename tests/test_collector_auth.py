import os
import unittest
from unittest.mock import patch

from collector.bitget_auth import (
    AUTH_ALLOWED,
    auth_headers,
    credentials,
    load_fee_map,
    sign,
)

from fakes import FakeResponse, FakeSession


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def test_signature_is_deterministic_and_query_sensitive(self):
        first = sign("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        same = sign("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=USDT-FUTURES")
        changed = sign("secret", "1700000000000", "GET", "/api/v3/account/all-fee-rate", "category=SPOT")
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)

    def test_credentials_accept_aliases(self):
        with patch.dict(os.environ, {
            "BITGET_KEY": "k", "BITGET_SECRET": "s", "BITGET_PASSPHRASE": "p",
        }, clear=True):
            self.assertEqual(credentials(), ("k", "s", "p"))

    def test_auth_headers_include_expected_fields(self):
        headers, query = auth_headers(
            "GET", "/api/v3/account/all-fee-rate", {"category": "USDT-FUTURES"},
            key="k", secret="s", passphrase="p", timestamp="1700000000000",
        )
        self.assertEqual(query, "category=USDT-FUTURES")
        self.assertEqual(headers["ACCESS-KEY"], "k")
        self.assertEqual(headers["ACCESS-PASSPHRASE"], "p")
        self.assertEqual(headers["ACCESS-TIMESTAMP"], "1700000000000")
        self.assertTrue(headers["ACCESS-SIGN"])

    def test_non_get_method_is_rejected(self):
        with self.assertRaises(ValueError):
            auth_headers("POST", "/api/v3/account/info", key="k", secret="s", passphrase="p")

    def test_non_allowlisted_path_is_rejected(self):
        with self.assertRaises(ValueError):
            auth_headers("GET", "/api/v3/trade/order", key="k", secret="s", passphrase="p")

    def test_only_two_account_paths_are_allowed(self):
        self.assertEqual(AUTH_ALLOWED, {"/api/v3/account/info", "/api/v3/account/all-fee-rate"})

    def test_missing_credentials_raise(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                auth_headers("GET", "/api/v3/account/info")

    async def test_load_fee_map_reads_permission_and_fees(self):
        env = {
            "BITGET_API_KEY": "k", "BITGET_API_SECRET": "s", "BITGET_API_PASSPHRASE": "p",
        }
        session = FakeSession([
            FakeResponse(200, {"code": "00000", "data": {"permType": "read-only"}}),
            FakeResponse(200, {"code": "00000", "data": [{"symbol": "BTCUSDT", "takerFeeRate": "0.0006"}]}),
        ])
        with patch.dict(os.environ, env, clear=True):
            fee_map, status = await load_fee_map(session)
        self.assertEqual(status, "OK_READ_ONLY_KEY")
        self.assertEqual(fee_map["BTCUSDT"]["takerFeeRate"], "0.0006")

    async def test_missing_credentials_return_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            fee_map, status = await load_fee_map(FakeSession([]))
        self.assertEqual(fee_map, {})
        self.assertEqual(status, "NOT_CONFIGURED")

    async def test_failure_does_not_echo_exception_text(self):
        env = {
            "BITGET_API_KEY": "k", "BITGET_API_SECRET": "s", "BITGET_API_PASSPHRASE": "p",
        }
        session = FakeSession([RuntimeError("secret=abc")] * 3)
        with patch.dict(os.environ, env, clear=True):
            _, status = await load_fee_map(session)
        self.assertNotIn("abc", status)
        self.assertTrue(status.startswith("AUTH_FAILED"))


if __name__ == "__main__":
    unittest.main()
