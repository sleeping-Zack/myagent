import asyncio
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


_REDIS_ALLOW_SCRIPT = """
local minute_key = KEYS[1]
local daily_key = KEYS[2]
local now = tonumber(ARGV[1])
local member = ARGV[2]
local minute_limit = tonumber(ARGV[3])
local daily_limit = tonumber(ARGV[4])
local count_daily = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', minute_key, '-inf', now - 60)
if redis.call('ZCARD', minute_key) >= minute_limit then
  return 0
end
if count_daily == 1 and tonumber(redis.call('GET', daily_key) or '0') >= daily_limit then
  return 0
end

redis.call('ZADD', minute_key, now, member)
redis.call('EXPIRE', minute_key, 61)
if count_daily == 1 then
  redis.call('INCR', daily_key)
  redis.call('EXPIRE', daily_key, 172800)
end
return 1
"""


class ChatRateLimiter:
    def __init__(self, namespace: str = "test", redis_url: str = "") -> None:
        self._namespace = namespace
        self._redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        ) if redis_url else None
        self._lock = asyncio.Lock()
        self._minute_requests: dict[str, deque[float]] = defaultdict(deque)
        self._daily_count = 0
        self._daily_date = date.min
        self._last_cleanup = 0.0

    async def allow(
        self,
        client_key: str,
        minute_limit: int,
        daily_limit: int,
        now: Optional[datetime] = None,
        count_daily: bool = True,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        if self._redis is not None:
            try:
                allowed = await self._redis.eval(
                    _REDIS_ALLOW_SCRIPT,
                    2,
                    f"rate:{self._namespace}:minute:{client_key}",
                    f"rate:{self._namespace}:daily:{now.date().isoformat()}",
                    now.timestamp(),
                    uuid4().hex,
                    minute_limit,
                    daily_limit,
                    int(count_daily),
                )
                return bool(allowed)
            except RedisError:
                pass
        return await self._allow_memory(
            client_key, minute_limit, daily_limit, now, count_daily
        )

    async def is_healthy(self) -> bool:
        if self._redis is None:
            return True
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    async def _allow_memory(
        self,
        client_key: str,
        minute_limit: int,
        daily_limit: int,
        now: datetime,
        count_daily: bool,
    ) -> bool:
        timestamp = now.timestamp()
        async with self._lock:
            if timestamp - self._last_cleanup >= 60:
                cutoff = timestamp - 60
                for key, key_requests in list(self._minute_requests.items()):
                    while key_requests and key_requests[0] <= cutoff:
                        key_requests.popleft()
                    if not key_requests:
                        del self._minute_requests[key]
                self._last_cleanup = timestamp

            if self._daily_date != now.date():
                self._daily_date = now.date()
                self._daily_count = 0

            requests = self._minute_requests[client_key]
            while requests and timestamp - requests[0] >= 60:
                requests.popleft()
            if len(requests) >= minute_limit or (
                count_daily and self._daily_count >= daily_limit
            ):
                return False

            requests.append(timestamp)
            if count_daily:
                self._daily_count += 1
            return True


_redis_url = get_settings().redis_url
chat_rate_limiter = ChatRateLimiter("chat", _redis_url)
feedback_rate_limiter = ChatRateLimiter("feedback", _redis_url)
visitor_create_rate_limiter = ChatRateLimiter("visitor", _redis_url)
conversation_create_rate_limiter = ChatRateLimiter("conversation", _redis_url)
admin_auth_rate_limiter = ChatRateLimiter("admin", _redis_url)
