"""Assigning to a name makes it local for the whole function."""

total = 0


def add(n):
    """Add n to total, forgetting the global declaration."""
    # error: UnboundLocalError: cannot access local variable 'total'
    # where it is not associated with a value
    total += n  # noqa: F823
    return total


def main() -> None:
    """Trigger the UnboundLocalError on purpose."""
    print(add(1))


if __name__ == "__main__":
    main()
