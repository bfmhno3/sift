"""Unpacking: star, swap, nested, slice assignment."""


def main() -> None:
    """Print one example per feature."""
    first, *middle, last = [1, 2, 3, 4, 5]
    print(first, middle, last)
    head, *_ = "sift"
    print(head)
    a, b = 1, 2
    a, b = b, a
    print("swap:", a, b)
    (x, y), (z, *rest) = (1, 2), (3, 4, 5)
    print("nested:", x, y, z, rest)
    for key, (lo, hi) in {"a": (1, 2), "b": (3, 4)}.items():
        print(key, lo, hi)
    merged = [*range(3), *"ab"]
    print("star in literal:", merged)
    print("dict merge:", {**{"a": 1}, **{"b": 2, "a": 3}})

    items = [0, 1, 2, 3, 4, 5]
    items[1:3] = ["x", "y", "z"]
    print("slice assignment grows:", items)
    items[::2] = [10, 20, 30, 40]
    print("extended slice, same size:", items)
    del items[1:3]
    print("del slice:", items)
    items[2:2] = ["ins"]
    print("insert by empty slice:", items)


if __name__ == "__main__":
    main()
