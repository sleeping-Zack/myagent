from collections import defaultdict, deque
from datetime import date, datetime, timezone
from threading import Lock
from typing import Optional


class ChatRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._minute_requests: dict[str, deque[float]] = defaultdict(deque)
        self._daily_count = 0
        self._daily_date = date.min

    def allow(
        self,
        client_key: str,
        minute_limit: int,
        daily_limit: int,
        now: Optional[datetime] = None,
        count_daily: bool = True,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        timestamp = now.timestamp()

        with self._lock:
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


chat_rate_limiter = ChatRateLimiter()
feedback_rate_limiter = ChatRateLimiter()
