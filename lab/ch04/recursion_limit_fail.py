"""Python has no tail-call optimization (expected failure)."""

import sys


def count_down(n):
    """Count down to zero in tail-call form."""
    if n == 0:
        return 0
    return count_down(n - 1)


def main() -> None:
    """Recurse past the limit on purpose."""
    print(sys.getrecursionlimit())
    print(count_down(500))
    # error: RecursionError: maximum recursion depth exceeded
    print(count_down(10**6))


if __name__ == "__main__":
    main()
