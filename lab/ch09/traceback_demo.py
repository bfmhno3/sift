"""The traceback module: format, walk and the 3.14 suggestions."""

import traceback

from sift.query import parse


def inner() -> None:
    """Raise through two frames."""
    parse("(rust")


def outer() -> None:
    """Call inner, so the traceback has two sift-side frames."""
    inner()


def main() -> None:
    """Capture a traceback three ways and print the pieces."""
    try:
        outer()
    except Exception as exc:
        print("-- format_exception_only")
        print("".join(traceback.format_exception_only(exc)), end="")

        print("-- walk_tb: file, function, line")
        for frame, lineno in traceback.walk_tb(exc.__traceback__):
            code = frame.f_code
            print(f"  {code.co_name} line {lineno}")

        print("-- StackSummary entries")
        summary = traceback.extract_tb(exc.__traceback__)
        for entry in summary:
            print(f"  {entry.name}: {entry.line}")

        print("-- TracebackException.format(chain=False) last line")
        tbe = traceback.TracebackException.from_exception(exc)
        print("  " + list(tbe.format(chain=False))[-1].strip())

    print("-- suggestions are computed by the traceback module (3.12+)")
    try:
        "abc".uper()
    except AttributeError as exc:
        print("".join(traceback.format_exception_only(exc)), end="")

    print("-- NameError suggestions")
    try:
        prnt("x")  # noqa: F821
    except NameError as exc:
        print("".join(traceback.format_exception_only(exc)), end="")

    print("-- print_exc goes to stderr, format_exc returns a string")
    try:
        {}["x"]
    except KeyError:
        text = traceback.format_exc()
    print("  lines in format_exc():", len(text.splitlines()))


if __name__ == "__main__":
    main()
