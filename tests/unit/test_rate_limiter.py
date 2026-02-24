"""Unit tests for the async rate limiter."""

import asyncio
import time

import pytest
import pytest_asyncio

from src.utils.rate_limiter import AsyncRateLimiter, RateLimitConfig, _is_rate_limit_error


class TestRateLimitConfig:
    def test_default_max_concurrent(self):
        cfg = RateLimitConfig(requests_per_second=2.0)
        assert cfg.max_concurrent == 5

    def test_custom_config(self):
        cfg = RateLimitConfig(requests_per_second=10.0, max_concurrent=3)
        assert cfg.requests_per_second == 10.0
        assert cfg.max_concurrent == 3


class TestAsyncRateLimiter:
    @pytest.mark.asyncio
    async def test_throttled_context_manager(self):
        limiter = AsyncRateLimiter()
        called = False

        async with limiter.throttled("tavily"):
            called = True

        assert called

    @pytest.mark.asyncio
    async def test_with_backoff_success(self):
        limiter = AsyncRateLimiter()
        result = await limiter.with_backoff("openai", lambda: asyncio.sleep(0) or "ok")
        # coroutine returns None from sleep(0), so test that no exception raised
        assert result is None  # asyncio.sleep(0) returns None

    @pytest.mark.asyncio
    async def test_with_backoff_actual_result(self):
        limiter = AsyncRateLimiter()

        async def coro():
            return 42

        result = await limiter.with_backoff("openai", coro)
        assert result == 42

    @pytest.mark.asyncio
    async def test_with_backoff_raises_on_max_attempts(self):
        limiter = AsyncRateLimiter()
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("rate limit exceeded — 429")

        with pytest.raises(Exception, match="429"):
            await limiter.with_backoff("tavily", always_fail, max_attempts=2)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_unknown_api_gets_default_config(self):
        limiter = AsyncRateLimiter()
        async with limiter.throttled("unknown_api_xyz"):
            pass  # Should not raise


class TestIsRateLimitError:
    def test_429_in_message(self):
        assert _is_rate_limit_error(Exception("HTTP 429 Too Many Requests"))

    def test_rate_limit_in_message(self):
        assert _is_rate_limit_error(Exception("rate limit exceeded"))

    def test_quota_in_message(self):
        assert _is_rate_limit_error(Exception("quota exceeded"))

    def test_unrelated_error(self):
        assert not _is_rate_limit_error(Exception("connection refused"))

    def test_case_insensitive(self):
        assert _is_rate_limit_error(Exception("RATE LIMIT"))
