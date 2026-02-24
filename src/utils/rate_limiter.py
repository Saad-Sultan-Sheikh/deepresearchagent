"""Token-bucket rate limiter with asyncio.Semaphore and exponential backoff."""

from __future__ import annotations

import asyncio
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator


@dataclass
class RateLimitConfig:
    requests_per_second: float
    max_concurrent: int = 5
    base_backoff_ms: float = 500.0
    max_backoff_ms: float = 30_000.0


# Per-API rate limit configs
RATE_LIMIT_CONFIGS: dict[str, RateLimitConfig] = {
    "tavily": RateLimitConfig(requests_per_second=2.0, max_concurrent=2),
    "brave": RateLimitConfig(requests_per_second=1.0, max_concurrent=1),
    "exa": RateLimitConfig(requests_per_second=0.5, max_concurrent=3),  # 30/min
    "claude": RateLimitConfig(requests_per_second=0.83, max_concurrent=5),  # 50/min
    "openai": RateLimitConfig(requests_per_second=8.33, max_concurrent=10),  # 500/min
    "gemini": RateLimitConfig(requests_per_second=1.0, max_concurrent=5),  # 60/min
}


@dataclass
class _APIBucket:
    config: RateLimitConfig
    semaphore: asyncio.Semaphore = field(init=False)
    _last_request_at: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self) -> None:
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._lock = asyncio.Lock()

    async def _wait_for_token(self) -> None:
        async with self._lock:
            now = time.monotonic()
            min_interval = 1.0 / self.config.requests_per_second
            elapsed = now - self._last_request_at
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_at = time.monotonic()


class AsyncRateLimiter:
    """Central rate limiter for all external API calls."""

    def __init__(self) -> None:
        self._buckets: dict[str, _APIBucket] = {}

    def _get_bucket(self, api: str) -> _APIBucket:
        if api not in self._buckets:
            cfg = RATE_LIMIT_CONFIGS.get(api, RateLimitConfig(requests_per_second=1.0))
            self._buckets[api] = _APIBucket(config=cfg)
        return self._buckets[api]

    @asynccontextmanager
    async def throttled(self, api: str) -> AsyncGenerator[None, None]:
        """Async context manager that enforces rate limits for the given API."""
        bucket = self._get_bucket(api)
        async with bucket.semaphore:
            await bucket._wait_for_token()
            yield

    async def with_backoff(
        self,
        api: str,
        coro_factory,
        max_attempts: int = 4,
    ):
        """Execute coro_factory() under rate limiting with exponential backoff on 429."""
        bucket = self._get_bucket(api)
        cfg = bucket.config

        for attempt in range(max_attempts):
            try:
                async with self.throttled(api):
                    return await coro_factory()
            except Exception as exc:
                is_rate_error = _is_rate_limit_error(exc)
                if not is_rate_error or attempt == max_attempts - 1:
                    raise
                delay_ms = min(
                    cfg.base_backoff_ms * (2**attempt) + random.uniform(0, 200),
                    cfg.max_backoff_ms,
                )
                await asyncio.sleep(delay_ms / 1000.0)

        raise RuntimeError(f"Max retry attempts ({max_attempts}) exceeded for {api}")


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect 429 / 529 / rate-limit / overloaded errors across different SDKs."""
    msg = str(exc).lower()
    return any(
        indicator in msg
        for indicator in ("429", "529", "rate limit", "ratelimit", "too many requests", "quota", "overloaded")
    )


# Module-level singleton
rate_limiter = AsyncRateLimiter()
