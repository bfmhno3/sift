"""Adding None to an int raises TypeError (expected failure)."""


def find_count(table: dict[str, int], key: str) -> int | None:
    """Return the count for key, or None if it is missing."""
    return table.get(key)


def main() -> None:
    """Trigger the TypeError on purpose."""
    counts = {"rust": 3}
    # error: TypeError: unsupported operand type(s) for +: 'NoneType'
    # and 'int'
    print(find_count(counts, "python") + 1)


if __name__ == "__main__":
    main()
