"""tuple vs list: size, immutability, hashing, frozenset."""

import sys


def main() -> None:
    """Print the differences that matter."""
    for n in (0, 1, 4, 10):
        t = tuple(range(n))
        xs = list(range(n))
        print(
            f"n={n:>2}: tuple {sys.getsizeof(t):>3} B, "
            f"list {sys.getsizeof(xs):>3} B"
        )
    t = (1, 2, 3)
    try:
        t[0] = 9  # type: ignore[index]
    except TypeError as exc:
        print("TypeError:", exc)
    inner = ([1], 2)
    inner[0].append(99)
    print("tuple holding a list can still change:", inner)
    try:
        hash(inner)
    except TypeError as exc:
        print("TypeError:", exc)
    grid = {(0, 1): "a", (1, 0): "b"}
    print("tuple as dict key:", grid[(0, 1)])
    print("hash((1, 2)) == hash((1, 2)):", hash((1, 2)) == hash((1, 2)))
    key = frozenset({"rust", "python"})
    print("frozenset as key:", {key: 1}[frozenset({"python", "rust"})])
    print("set ops:", {1, 2, 3} & {2, 3, 4}, {1, 2} | {2, 3}, {1, 2} - {2})


if __name__ == "__main__":
    main()
