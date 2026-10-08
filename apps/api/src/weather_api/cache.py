"""A small in-process cache: the boundary where Redis can be added later.

Forecast data for a (grid point, model run) pair never changes once written,
so it is safe to cache indefinitely; a new run simply produces a new key.
Because the key is the grid point, not the user, every location sharing a
grid cell shares one cache entry.

Each Cloud Run instance keeps its own copy. When traffic justifies it, replace
TTLCache with a Redis-backed class exposing the same get/set methods.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any


class TTLCache:
    def __init__(self, max_entries: int = 512, ttl_seconds: float = 3600) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl_seconds, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


forecast_cache = TTLCache()
