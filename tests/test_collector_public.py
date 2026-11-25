import asyncio
import unittest

import aiohttp

from collector.bitget_public import (
    BitgetAPIError,
    ForbiddenEndpoint,
    PublicClient,
    TokenBucket,
)

from fakes import FakeClock, FakeResponse, FakeSession, make_sleep


class PublicClientTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self, responses, clock=None):
        clock = clock or FakeClock()
        limiter = TokenBucket(1000, 1000, clock=clock, sleep=make_sleep(clock))
        session = FakeSession(responses)
        client = PublicClient(
            session,
            limiter=limiter,
            sleep=make_sleep(clock),
            rand=lambda: 0.0,
            max_attempts=3,
        )
        return client, session, clock

    async def test_forbidden_endpoint_is_rejected(self):
        client, _, _ = self.make_client([])
        with self.assertRaises(ForbiddenEndpoint):
            await client.get("/api/v3/trade/place-order")

    async def test_retry_on_429_then_success(self):
        client, session, _ = self.make_client([
            FakeResponse(429),
            FakeResponse(200, {"code": "00000", "data": [1]}),
        ])
        payload = await client.get("/api/v3/market/tickers")
        self.assertEqual(payload["data"], [1])
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(client.stats.requests, 1)
        self.assertEqual(client.stats.retries, 1)
        self.assertEqual(client.stats.rate_limit_events, 1)

    async def test_non_retryable_http_error(self):
        client, _, _ = self.make_client([FakeResponse(400, text="bad request")])
        with self.assertRaises(BitgetAPIError):
            await client.get("/api/v3/market/tickers")

    async def test_bitget_error_code(self):
        client, _, _ = self.make_client([
            FakeResponse(200, {"code": "40004", "msg": "invalid symbol"}),
        ])
        with self.assertRaises(BitgetAPIError):
            await client.get("/api/v3/market/tickers")

    async def test_gather_returns_per_call_exceptions(self):
        client, _, _ = self.make_client([
            FakeResponse(400, text="bad"),
            FakeResponse(200, {"code": "00000", "data": [2]}),
        ])
        results = await client.gather([
            ("/api/v3/market/tickers", None),
            ("/api/v3/market/candles", {"symbol": "BTCUSDT"}),
        ])
        self.assertIsInstance(results[0], Exception)
        self.assertEqual(results[1]["data"], [2])

    async def test_rate_policy_reduces_after_excess_429(self):
        client, _, _ = self.make_client([])
        client.stats.attempts = 100
        client.stats.rate_limit_events = 2
        client._maybe_adapt()
        self.assertEqual(client.limiter.rate_per_sec, 10.0)
        self.assertTrue(client.stats.rate_policy["adapted"])

    async def test_token_bucket_waits_for_capacity(self):
        clock = FakeClock(0.0)
        bucket = TokenBucket(1.0, 1, clock=clock, sleep=make_sleep(clock))
        await bucket.acquire()
        await bucket.acquire()
        self.assertAlmostEqual(clock.value, 1.0, places=6)

    async def test_client_error_is_wrapped_without_leaking_url(self):
        clock = FakeClock()
        client = PublicClient(
            FakeSession([aiohttp.ClientError("boom"), aiohttp.ClientError("boom"),
                         aiohttp.ClientError("boom")]),
            limiter=TokenBucket(1000, 1000, clock=clock, sleep=make_sleep(clock)),
            sleep=make_sleep(clock),
            rand=lambda: 0.0,
        )
        with self.assertRaises(RuntimeError) as caught:
            await client.get("/api/v3/market/tickers")
        self.assertNotIn("boom", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
