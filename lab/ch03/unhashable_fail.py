"""A list cannot be a dict key (expected failure)."""


def main() -> None:
    """Trigger the TypeError on purpose."""
    # error: TypeError: unhashable type: 'list'
    table = {[1]: 2}
    print(table)


if __name__ == "__main__":
    main()
