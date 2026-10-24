"""A small least-recently-used cache."""

from collections import OrderedDict
from collections.abc import Callable


class LRUCache[K, V]:
    """Keep the maxsize most recently used entries.

    A read or a write moves the key to the fresh end of an
    OrderedDict; when the cache is full, the key at the stale end is
    evicted. ``hits`` and ``misses`` count the lookups made through
    ``get``, ``__getitem__`` and ``get_or_set``.
    """

    def __init__(self, maxsize: int) -> None:
        """Create an empty cache; maxsize must be at least 1."""
        if maxsize < 1:
            raise ValueError(f"maxsize must be at least 1, got {maxsize}")
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self._data: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        """Return the value of key and refresh it, or None."""
        try:
            value = self._data[key]
        except KeyError:
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return value

    def __getitem__(self, key: K) -> V:
        """Return the value of key and refresh it; KeyError if absent."""
        try:
            value = self._data[key]
        except KeyError:
            self.misses += 1
            raise
        self._data.move_to_end(key)
        self.hits += 1
        return value

    def __setitem__(self, key: K, value: V) -> None:
        """Store value, evicting the stalest entry when full."""
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def get_or_set(self, key: K, make: Callable[[K], V]) -> V:
        """Return the value of key, computing make(key) on a miss.

        A cached None is a hit; only an absent key calls make.
        """
        try:
            return self[key]
        except KeyError:
            value = make(key)
            self[key] = value
            return value

    def __contains__(self, key: object) -> bool:
        """Return True if key is cached, without refreshing it."""
        return key in self._data

    def __len__(self) -> int:
        """Return the number of cached entries."""
        return len(self._data)

    def clear(self) -> None:
        """Drop every entry and reset the counters."""
        self._data.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """Return hits / (hits + misses), or 0.0 before any lookup."""
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
