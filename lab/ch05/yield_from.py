"""yield from: delegating to a sub-iterator and taking its result."""

from collections.abc import Iterator


def chars(text: str) -> Iterator[str]:
    """Yield the characters of text, then return their count."""
    yield from text
    return len(text)


def flat_manual(parts: list[str]) -> Iterator[str]:
    """Delegate by hand with an inner for loop."""
    for part in parts:
        # the loop that yield from replaces
        for ch in chars(part):  # noqa: UP028
            yield ch


def flat_delegating(parts: list[str]) -> Iterator[str]:
    """Delegate with yield from, collecting each return value."""
    total = 0
    for part in parts:
        total += yield from chars(part)
    print("  total returned by sub-generators:", total)


def walk(tree: object) -> Iterator[int]:
    """Yield the leaves of nested lists, depth first."""
    if isinstance(tree, list):
        for child in tree:
            yield from walk(child)
    else:
        yield tree


def main() -> None:
    """Compare the loop with yield from and flatten a tree."""
    parts = ["ab", "cde", "f"]
    print("manual:    ", "".join(flat_manual(parts)))
    print("delegating:", "".join(flat_delegating(parts)))
    print("walk:", list(walk([1, [2, [3, 4]], [[5]], 6])))

    gen = chars("xy")
    print(next(gen), next(gen))
    try:
        next(gen)
    except StopIteration as stop:
        print("StopIteration.value:", stop.value)


if __name__ == "__main__":
    main()
