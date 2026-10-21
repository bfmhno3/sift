"""PEP 479: StopIteration inside a generator becomes RuntimeError."""

from collections.abc import Iterator


def first_words(lines: list[list[str]]) -> Iterator[str]:
    """Yield the first word of each line; a bug on empty lines."""
    for words in lines:
        # BAD: next() on an empty iterator raises StopIteration here
        yield next(iter(words))


def main() -> None:
    """Run the buggy generator on input with an empty line."""
    lines = [["alpha", "beta"], [], ["gamma"]]
    # error: RuntimeError: generator raised StopIteration
    print(list(first_words(lines)))


if __name__ == "__main__":
    main()
