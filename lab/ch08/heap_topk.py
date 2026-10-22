"""heapq.nlargest against sorting everything, at 1e6 scores."""

import heapq
import random
import statistics
import time
from collections.abc import Callable

N = 1_000_000
K = 10
REPEATS = 5


def median_ms(fn: Callable[[], object]) -> float:
    """Return the median wall time of fn() in milliseconds."""
    runs = []
    for _ in range(REPEATS):
        start = time.perf_counter_ns()
        fn()
        runs.append((time.perf_counter_ns() - start) / 1e6)
    return statistics.median(runs)


def main() -> None:
    """Time both ways to pick the 10 best of a million scores."""
    rng = random.Random(1234)
    scores = {doc_id: rng.random() for doc_id in range(N)}

    def key(item: tuple[int, float]) -> tuple[float, int]:
        """Order by score, then by smaller doc_id."""
        return (item[1], -item[0])

    def by_heap() -> list[tuple[int, float]]:
        """Keep a heap of K items."""
        return heapq.nlargest(K, scores.items(), key=key)

    def by_sort() -> list[tuple[int, float]]:
        """Sort a million items, keep K."""
        return sorted(scores.items(), key=key, reverse=True)[:K]

    assert by_heap() == by_sort()
    heap_ms, sort_ms = median_ms(by_heap), median_ms(by_sort)
    print(f"{N} scores, k = {K}, median of {REPEATS} runs")
    print(f"heapq.nlargest {heap_ms:9.1f} ms")
    print(f"sorted()[:k]   {sort_ms:9.1f} ms")
    print(f"sorted / nlargest = {sort_ms / heap_ms:.2f}x")


if __name__ == "__main__":
    main()
