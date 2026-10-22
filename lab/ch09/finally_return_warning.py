"""PEP 765 (3.14): return in a finally block is a SyntaxWarning."""


def swallow() -> str:
    """Raise, then lose the exception in the finally block."""
    try:
        raise RuntimeError("this error disappears")
    finally:
        return "finally won"  # BAD: hides the error  # noqa: B012


def main() -> None:
    """Call swallow and print what it returns."""
    print(swallow())


if __name__ == "__main__":
    main()
