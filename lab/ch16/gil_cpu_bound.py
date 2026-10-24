"""One CPU-bound function on 1 and on 4 threads, GIL build."""

import sys
import threading
import time

LIMIT = 2_000_000
BLOCKS = 40
THREADS = 4


def count_primes(lo: int, hi: int) -> int:
    """Count the primes in [lo, hi) by trial division; pure Python."""
    count = 0
    for n in range(max(lo, 2), hi):
        if n % 2 == 0:
            count += n == 2
            continue
        divisor = 3
        while divisor * divisor <= n:
            if n % divisor == 0:
                break
            divisor += 2
        else:
            count += 1
    return count


def run_threads(count: int) -> tuple[float, int]:
    """Share the BLOCKS blocks of [0, LIMIT) among count threads.

    Thread i takes blocks i, i + count, i + 2 * count, ... so every
    thread gets small and large numbers. Return the seconds and the
    number of primes found.
    """
    size = LIMIT // BLOCKS
    found = [0] * count

    def part(i: int) -> None:
        for block in range(i, BLOCKS, count):
            found[i] += count_primes(block * size, (block + 1) * size)

    threads = [threading.Thread(target=part, args=(i,)) for i in range(count)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return time.perf_counter() - start, sum(found)


def main() -> None:
    """Time the same total work on 1 and on THREADS threads."""
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"python {sys.version.split()[0]}, GIL enabled: {gil}")
    one, primes_one = run_threads(1)
    many, primes_many = run_threads(THREADS)
    print(f"primes below {LIMIT}: {primes_one} (1 thread)")
    print(f"primes below {LIMIT}: {primes_many} ({THREADS} threads)")
    print("timing lines (vary between runs):")
    print(f"  1 thread  : {one:6.3f} s")
    print(f"  {THREADS} threads : {many:6.3f} s")
    print(f"  speedup   : {one / many:6.2f}x")


if __name__ == "__main__":
    main()
