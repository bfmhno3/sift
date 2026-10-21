"""Measure big-O: append vs insert(0) vs deque, list vs set lookup."""

import timeit


def per_op_ns(stmt: str, setup: str, number: int) -> float:
    """Return the best-of-5 nanoseconds per execution of stmt."""
    runs = timeit.repeat(stmt, setup, repeat=5, number=number)
    return min(runs) / number * 1e9


def front_insert() -> None:
    """Compare appending at the back with inserting at the front."""
    print("push 1 item, container already holds n items (ns per op)")
    print(f"{'n':>9} {'append':>9} {'insert(0)':>10} {'appendleft':>11}")
    for n in (10**3, 10**4, 10**5):
        setup = (
            "from collections import deque; "
            f"xs = list(range({n})); dq = deque(range({n}))"
        )
        append = per_op_ns("xs.append(0); xs.pop()", setup, 2000)
        insert = per_op_ns("xs.insert(0, 0); xs.pop(0)", setup, 200)
        left = per_op_ns("dq.appendleft(0); dq.popleft()", setup, 2000)
        print(f"{n:>9} {append:>9.0f} {insert:>10.0f} {left:>11.0f}")


def membership() -> None:
    """Compare x in list with x in set; the probe is the worst case."""
    print("\nx in container, x absent (ns per op)")
    print(f"{'n':>9} {'list':>12} {'set':>9} {'speedup':>10}")
    for n in (10**3, 10**4, 10**5, 10**6):
        setup = f"xs = list(range({n})); ss = set(xs); x = -1"
        number = max(1, 2_000_000 // n)
        in_list = per_op_ns("x in xs", setup, number)
        in_set = per_op_ns("x in ss", setup, 100_000)
        print(
            f"{n:>9} {in_list:>12.0f} {in_set:>9.0f} {in_list / in_set:>9.0f}x"
        )


def main() -> None:
    """Run both experiments."""
    front_insert()
    membership()


if __name__ == "__main__":
    main()
