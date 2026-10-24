"""I/O-bound work scales with threads, even with the GIL."""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CORPUS = Path("corpus/posts")


def wait_for_the_network(_: int) -> None:
    """Stand in for a request: the thread sleeps, the GIL is free."""
    time.sleep(0.1)


def read_file(path: Path) -> int:
    """Read one file; the GIL is released during the read call."""
    return len(path.read_bytes())


def timed_sleep(workers: int, jobs: int = 16) -> float:
    """Run jobs sleeps of 0.1 s on workers threads; return seconds."""
    start = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(wait_for_the_network, range(jobs)))
    return time.perf_counter() - start


def timed_reads(workers: int, paths: list[Path]) -> tuple[float, int]:
    """Read every path on workers threads; return seconds and bytes."""
    start = time.perf_counter()
    with ThreadPoolExecutor(workers) as pool:
        total = sum(pool.map(read_file, paths))
    return time.perf_counter() - start, total


def main() -> None:
    """Time sleeps and file reads on 1, 2, 4, 8 and 16 threads."""
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"python {sys.version.split()[0]}, GIL enabled: {gil}")
    paths = sorted(CORPUS.rglob("*.md"))
    print(f"{len(paths)} files, 16 sleeps of 0.1 s")
    print("timing lines (vary between runs):")
    print("  workers  16 sleeps (ideal)    reads of all files")
    totals = set()
    for workers in (1, 2, 4, 8, 16):
        slept = timed_sleep(workers)
        read, total = timed_reads(workers, paths)
        totals.add(total)
        print(
            f"  {workers:>7}  {slept:6.3f} s ({1.6 / workers:5.3f} s)"
            f"    {read * 1000:7.2f} ms"
        )
    print("bytes read, the same for every worker count:", totals)
    print("active threads at the end:", threading.active_count())


if __name__ == "__main__":
    main()
