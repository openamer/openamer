"""In-memory response cache with least-recently-used eviction."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class CacheStore:
    """Bounded key/value store; oldest reads are dropped first."""

    def __init__(self, capacity: int = 128) -> None:
        self.capacity = capacity
        self._entries: OrderedDict[str, Any] = OrderedDict()

    def lookup(self, key: str) -> Any | None:
        """Return the cached value for *key*, marking it as recently used."""
        if key not in self._entries:
            return None
        self._entries.move_to_end(key)
        return self._entries[key]

    def store(self, key: str, value: Any) -> None:
        """Insert *value*; evict when the store is over capacity."""
        self._entries[key] = value
        self._entries.move_to_end(key)
        if len(self._entries) > self.capacity:
            self.evict_lru()

    def evict_lru(self) -> None:
        """Drop the least recently used entry, if any."""
        if self._entries:
            self._entries.popitem(last=False)
