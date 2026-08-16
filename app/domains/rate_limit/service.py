import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int

    def headers(self) -> dict[str, str]:
        return {
            "x-ratelimit-limit-requests": str(self.limit),
            "x-ratelimit-remaining-requests": str(self.remaining),
            "x-ratelimit-reset-requests": str(self.reset_epoch),
        }


class RateLimiter:
    """Redis-backed fixed-window rate limiter.

    Redis is intentionally scoped to ephemeral coordination here. Durable agent
    configuration and chat memory live in PostgreSQL; semantic knowledge lives in Qdrant.
    """

    def __init__(self, redis: Redis, requests: int, window_seconds: int) -> None:
        self.redis = redis
        self.requests = requests
        self.window_seconds = window_seconds

    async def check(self, api_key_id: int) -> RateLimitResult:
        now = int(time.time())
        window = now // self.window_seconds
        reset = (window + 1) * self.window_seconds
        key = f"rl:{api_key_id}:{window}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, self.window_seconds + 1)
        remaining = max(0, self.requests - current)
        return RateLimitResult(current <= self.requests, self.requests, remaining, reset)
