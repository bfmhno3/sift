"""List over-allocation: sys.getsizeof across appends, and array."""

import sys
from array import array


def growth_steps(n: int) -> list[tuple[int, int]]:
    """Return (length, bytes) each time append grows the buffer."""
    items: list[int] = []
    steps = [(0, sys.getsizeof(items))]
    for i in range(n):
        items.append(i)
        size = sys.getsizeof(items)
        if size != steps[-1][1]:
            steps.append((len(items), size))
    return steps


def main() -> None:
    """Print the growth steps and a list vs array memory comparison."""
    steps = growth_steps(1000)
    print(f"{'len':>5} {'bytes':>7} {'slots':>6}")
    header = sys.getsizeof([])
    for length, size in steps:
        print(f"{length:>5} {size:>7} {(size - header) // 8:>6}")
    print("lengths at each resize:", [s[0] for s in steps[1:]])
    print("literal [0,1,2,3]:", sys.getsizeof([0, 1, 2, 3]), "bytes")
    print("list(range(4)):", sys.getsizeof(list(range(4))), "bytes")
    n = 100_000
    as_list = list(range(n))
    as_array = array("i", range(n))
    list_total = sys.getsizeof(as_list) + sum(map(sys.getsizeof, as_list))
    print(f"list of {n} ints: {list_total} bytes (pointers + int objects)")
    print(f"array('i') of {n}: {sys.getsizeof(as_array)} bytes")
    print(f"ratio: {list_total / sys.getsizeof(as_array):.1f}x")


if __name__ == "__main__":
    main()
