"""Per-process sliding-window rate limiting for location creation and search.

Limits are per Cloud Run instance, which is adequate abuse protection for v1.
A shared limit across instances needs Redis (or Cloud Armor) later.
"""

import threading
import time
from collections import defaultdict, deque

from weather_api.errors import ApiError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise ApiError(429, "rate_limited", "Too many requests. Please wait a moment.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
