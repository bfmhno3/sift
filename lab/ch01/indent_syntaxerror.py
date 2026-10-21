"""Mixed tabs and spaces (expected failure).

The file itself is valid Python; the bad source lives in a string and
is compiled at runtime, so the TabError escapes and the process exits
with a traceback.
"""

BAD = "if True:\n        x = 1\n\ty = 2\n"
BAD_DEDENT = "if True:\n    x = 1\n  y = 2\n"


def main() -> None:
    """Show IndentationError, then raise TabError."""
    try:
        compile(BAD_DEDENT, "<dedent>", "exec")
    except IndentationError as exc:
        print("IndentationError:", exc.msg, "at line", exc.lineno)
    # error: TabError: inconsistent use of tabs and spaces in
    # indentation
    compile(BAD, "<mixed>", "exec")


if __name__ == "__main__":
    main()
