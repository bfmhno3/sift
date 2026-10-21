"""Peak memory and time: a list of all corpus tokens vs a stream."""

import statistics
import time
import tracemalloc
from collections.abc import Callable, Iterator
from pathlib import Path

from sift.analysis.tokenize import iter_tokens, tokenize
from sift.corpus import iter_documents

ROOT = Path("corpus/posts")
RUNS = 3


def bodies() -> Iterator[str]:
    """Yield the stripped body of every post, one at a time."""
    for doc in iter_documents(ROOT):
        yield doc.body


def count_with_list() -> int:
    """Hold every token of the corpus in one list, then count it."""
    tokens: list[str] = []
    for body in bodies():
        tokens.extend(tokenize(body))
    return len(tokens)


def count_with_stream() -> int:
    """Count the tokens as they pass, never holding more than one."""
    return sum(1 for body in bodies() for _ in iter_tokens(body))


def peak_kib(work: Callable[[], int]) -> tuple[int, float]:
    """Return the result of work and its tracemalloc peak in KiB."""
    tracemalloc.start()
    result = work()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak / 1024


def median_ms(work: Callable[[], int]) -> float:
    """Return the median wall time of work in milliseconds."""
    times = []
    for _ in range(RUNS):
        start = time.perf_counter_ns()
        work()
        times.append((time.perf_counter_ns() - start) / 1e6)
    return statistics.median(times)


def main() -> None:
    """Print token counts, peak memory and time for both versions."""
    n_list, peak_list = peak_kib(count_with_list)
    n_stream, peak_stream = peak_kib(count_with_stream)
    print(f"tokens via list:   {n_list}")
    print(f"tokens via stream: {n_stream}")
    print(f"same count: {n_list == n_stream}")
    print(f"peak memory, list:   {peak_list:10.0f} KiB")
    print(f"peak memory, stream: {peak_stream:10.0f} KiB")
    print(f"peak ratio list/stream: {peak_list / peak_stream:.1f}x")
    t_list = median_ms(count_with_list)
    t_stream = median_ms(count_with_stream)
    print(f"time, list:   {t_list:8.1f} ms (median of {RUNS})")
    print(f"time, stream: {t_stream:8.1f} ms (median of {RUNS})")
    print(f"time ratio stream/list: {t_stream / t_list:.2f}")

    # The same idea at toy size: [] materializes, () does not.
    squares_list = [n * n for n in range(100_000)]
    squares_gen = (n * n for n in range(100_000))
    print(f"list of 100000: {squares_list.__sizeof__()} bytes")
    print(f"genexp of 100000: {squares_gen.__sizeof__()} bytes")


if __name__ == "__main__":
    main()
