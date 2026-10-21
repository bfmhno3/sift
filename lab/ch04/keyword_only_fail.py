"""Passing a keyword-only parameter by position (expected failure)."""


def search(query, *, limit=10):
    """Return the query and limit."""
    return query, limit


def main() -> None:
    """Trigger the TypeError on purpose."""
    # error: TypeError: search() takes 1 positional argument but 2
    # were given
    print(search("kalman", 3))


if __name__ == "__main__":
    main()
