"""zip(strict=True) rejects iterables of different lengths."""


def main() -> None:
    """Show the silent truncation and then the strict failure."""
    names = ["a", "b", "c"]
    scores = [1, 2]
    print("default zip drops data:", list(zip(names, scores, strict=False)))
    # error: ValueError: zip() argument 2 is shorter than argument 1
    print(list(zip(names, scores, strict=True)))


if __name__ == "__main__":
    main()
