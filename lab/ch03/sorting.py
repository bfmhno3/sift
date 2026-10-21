"""sorted: key, stability, itemgetter, Timsort on presorted data."""

import random
import timeit
from operator import itemgetter


def main() -> None:
    """Show key functions, stability and the presorted-input speedup."""
    rows = [("tea", 3), ("bike", 1), ("rust", 3), ("pid", 2), ("gdb", 1)]
    print(sorted(rows, key=itemgetter(1)))
    print(sorted(rows, key=itemgetter(1), reverse=True))
    print(sorted(rows, key=lambda r: (-r[1], r[0])))
    print(sorted(["b", "A", "c", "B"], key=str.casefold))
    # 稳定性：key 相同的元素保持原来的相对顺序，reverse 也一样
    print([r[0] for r in sorted(rows, key=itemgetter(1), reverse=True)])

    rng = random.Random(1234)
    n = 1_000_000
    shuffled = [rng.random() for _ in range(n)]
    presorted = sorted(shuffled)
    reverse = presorted[::-1]
    for name, data in (
        ("shuffled", shuffled),
        ("presorted", presorted),
        ("reversed", reverse),
    ):
        best = min(timeit.repeat(lambda d=data: sorted(d), number=1, repeat=5))
        print(f"sorted {name:>9}, n={n}: {best * 1000:7.1f} ms")


if __name__ == "__main__":
    main()
