"""Tests for sift.cache."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sift.cache import LRUCache


def test_rejects_a_size_below_one() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        LRUCache[str, int](0)


def test_get_returns_none_for_a_missing_key() -> None:
    cache = LRUCache[str, int](2)
    assert cache.get("a") is None
    assert (cache.hits, cache.misses) == (0, 1)


def test_set_and_get_round_trip() -> None:
    cache = LRUCache[str, int](2)
    cache["a"] = 1
    assert cache.get("a") == 1
    assert cache["a"] == 1
    assert (cache.hits, cache.misses) == (2, 0)
    assert len(cache) == 1


def test_getitem_raises_keyerror_and_counts_a_miss() -> None:
    cache = LRUCache[str, int](2)
    with pytest.raises(KeyError):
        cache["a"]
    assert cache.misses == 1


def test_the_stalest_entry_is_evicted() -> None:
    cache = LRUCache[str, int](2)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3
    assert "a" not in cache
    assert "b" in cache
    assert "c" in cache


def test_a_read_refreshes_the_entry() -> None:
    cache = LRUCache[str, int](2)
    cache["a"] = 1
    cache["b"] = 2
    assert cache.get("a") == 1
    cache["c"] = 3
    assert "a" in cache
    assert "b" not in cache


def test_overwriting_refreshes_and_does_not_grow() -> None:
    cache = LRUCache[str, int](2)
    cache["a"] = 1
    cache["b"] = 2
    cache["a"] = 10
    cache["c"] = 3
    assert len(cache) == 2
    assert cache.get("a") == 10
    assert "b" not in cache


def test_contains_does_not_refresh_or_count() -> None:
    cache = LRUCache[str, int](2)
    cache["a"] = 1
    cache["b"] = 2
    assert "a" in cache
    cache["c"] = 3
    assert "a" not in cache
    assert (cache.hits, cache.misses) == (0, 0)


def test_get_or_set_computes_once() -> None:
    cache = LRUCache[str, int](2)
    calls: list[str] = []

    def make(key: str) -> int:
        calls.append(key)
        return len(key)

    assert cache.get_or_set("abc", make) == 3
    assert cache.get_or_set("abc", make) == 3
    assert calls == ["abc"]
    assert (cache.hits, cache.misses) == (1, 1)


def test_get_or_set_treats_a_cached_none_as_a_hit() -> None:
    cache = LRUCache[str, int | None](2)
    calls = 0

    def make(key: str) -> int | None:
        nonlocal calls
        calls += 1
        return None

    assert cache.get_or_set("a", make) is None
    assert cache.get_or_set("a", make) is None
    assert calls == 1


def test_hit_rate_and_clear() -> None:
    cache = LRUCache[str, int](2)
    assert cache.hit_rate == 0.0
    cache["a"] = 1
    cache.get("a")
    cache.get("b")
    assert cache.hit_rate == 0.5
    cache.clear()
    assert len(cache) == 0
    assert (cache.hits, cache.misses, cache.hit_rate) == (0, 0, 0.0)


@given(
    st.integers(min_value=1, max_value=5),
    st.lists(st.integers(min_value=0, max_value=8), max_size=60),
)
def test_matches_a_list_model(size: int, keys: list[int]) -> None:
    """The cache keeps exactly the last `size` distinct keys used."""
    cache = LRUCache[int, int](size)
    model: list[int] = []
    for key in keys:
        cache[key] = key * 2
        if key in model:
            model.remove(key)
        model.append(key)
        del model[:-size]
    assert len(cache) == len(model) <= size
    assert all(key in cache for key in model)
