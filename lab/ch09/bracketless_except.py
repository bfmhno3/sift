"""PEP 758 (3.14): except A, B without parentheses."""


def parse(raw: str) -> int | None:
    """Return int(raw), or None for text and for non-strings."""
    try:
        return int(raw)
    except ValueError, TypeError:
        return None


def main() -> None:
    """Catch two types with the new syntax, and show its limit."""
    for raw in ("42", "forty-two", None):
        print(f"parse({raw!r}) = {parse(raw)}")

    # `as` still needs the parentheses.
    try:
        int("x")
    except (ValueError, TypeError) as exc:
        print("with as:", type(exc).__name__)

    source = "try:\n    pass\nexcept ValueError, TypeError as e:\n    pass\n"
    try:
        compile(source, "<no-parens-with-as>", "exec")
    except SyntaxError as exc:
        # error: SyntaxError: multiple exception types must be
        # parenthesized when using 'as'
        print("no parentheses with as:", exc.msg)


if __name__ == "__main__":
    main()
