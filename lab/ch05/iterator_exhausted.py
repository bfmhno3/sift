"""An iterator is used up after one pass; lazy built-ins too."""


def main() -> None:
    """Show the second pass of an iterator and of lazy built-ins."""
    words = ["alpha", "beta", "gamma"]
    it = iter(words)
    print("first pass: ", list(it))
    print("second pass:", list(it))
    print("list again: ", list(words), list(words))

    squares = (n * n for n in range(4))
    print("genexp 1:", list(squares))
    print("genexp 2:", list(squares))

    # map, zip, enumerate and reversed are iterators: one pass only.
    pairs = zip("abc", range(3), strict=True)
    print("zip is iterator:", iter(pairs) is pairs)
    print("zip 1:", list(pairs))
    print("zip 2:", list(pairs))
    numbered = enumerate(words, start=1)
    print("enumerate:", next(numbered), next(numbered))
    backwards = reversed(words)
    print("reversed:", type(backwards).__name__, list(backwards))

    # range is a lazy sequence, not an iterator: reusable and indexable.
    big = range(10**12)
    print("range:", big, len(big), big[-1], 999 in big)
    print("range is iterator:", iter(big) is big)
    print("range twice:", list(range(3)), list(range(3)))

    # sorted(it) and sum(it) consume; len(it) is not defined.
    it = iter(words)
    print("has len:", hasattr(it, "__len__"))
    print("sorted:", sorted(it, reverse=True), "then", sorted(it))


if __name__ == "__main__":
    main()
