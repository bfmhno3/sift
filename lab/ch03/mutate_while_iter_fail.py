"""Changing a dict while iterating over it (expected failure)."""


def main() -> None:
    """Trigger the RuntimeError on purpose."""
    counts = {"a": 1, "b": 0, "c": 2}
    # error: RuntimeError: dictionary changed size during iteration
    for key, value in counts.items():
        if value == 0:
            del counts[key]
    print(counts)


if __name__ == "__main__":
    main()
