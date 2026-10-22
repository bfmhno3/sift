"""A small program to debug: the mean of a list, twice."""

import sys


def mean(values: list[float]) -> float:
    """Return the arithmetic mean of values."""
    total = 0.0
    for value in values:
        total += value
    return total / len(values)


def main() -> None:
    """Print two means; the second list is empty and fails."""
    if "--breakpoint" in sys.argv:
        breakpoint()
    print("mean of [1, 2, 3]:", mean([1, 2, 3]))
    print("mean of []:", mean([]))


if __name__ == "__main__":
    main()
