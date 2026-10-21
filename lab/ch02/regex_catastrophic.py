"""Catastrophic backtracking: (a+)+$ on a string that ends in b."""

import re
import time

LIMIT_S = 1.0
BAD = re.compile(r"(a+)+$")
GOOD = re.compile(r"a+$")


def timed_search(pattern: re.Pattern[str], text: str) -> float:
    """Return the seconds one search takes."""
    start = time.perf_counter()
    pattern.search(text)
    return time.perf_counter() - start


def main() -> None:
    """Grow the input until one search takes at least a second."""
    print(f"{'n':>3} {'(a+)+$ [ms]':>14} {'a+$ [ms]':>10} {'ratio':>6}")
    previous = 0.0
    for n in range(10, 64):
        text = "a" * n + "b"
        bad = timed_search(BAD, text)
        good = timed_search(GOOD, text)
        ratio = f"{bad / previous:.2f}" if previous else "-"
        print(f"{n:>3} {bad * 1000:>14.3f} {good * 1000:>10.3f} {ratio:>6}")
        previous = bad
        if bad >= LIMIT_S:
            print(f"stop: n={n} took {bad:.2f} s >= {LIMIT_S} s")
            break


if __name__ == "__main__":
    main()
