"""Exception chaining: __context__, __cause__ and from None."""

import traceback

from sift.errors import FrontMatterError
from sift.frontmatter import parse_front_matter


def translate() -> None:
    """Raise ValueError; inside an except block it gets chained."""
    raise ValueError("no title")


def show(label: str, exc: BaseException) -> None:
    """Print the chain attributes of exc."""
    print(f"-- {label}")
    print(f"  __cause__    = {exc.__cause__!r}")
    print(f"  __context__  = {exc.__context__!r}")
    print(f"  __suppress_context__ = {exc.__suppress_context__}")
    for line in traceback.format_exception_only(exc):
        print("  last line:", line.rstrip())


def main() -> None:
    """Raise the same error three ways and inspect the chain."""
    try:
        try:
            {}["title"]
        except KeyError:
            translate()  # raises while KeyError is being handled
    except ValueError as exc:
        show("implicit chaining", exc)
        text = "".join(traceback.format_exception(exc))
        print("  mentions 'During handling':", "During handling" in text)

    try:
        try:
            {}["title"]
        except KeyError as inner:
            raise ValueError("no title") from inner  # explicit: __cause__
    except ValueError as exc:
        show("raise ... from inner", exc)
        text = "".join(traceback.format_exception(exc))
        print("  mentions 'direct cause':", "direct cause" in text)

    try:
        try:
            {}["title"]
        except KeyError:
            raise ValueError("no title") from None  # hide the old one
    except ValueError as exc:
        show("raise ... from None", exc)
        text = "".join(traceback.format_exception(exc))
        print("  mentions KeyError at all:", "KeyError" in text)

    try:
        parse_front_matter("title: [oops")
    except FrontMatterError as exc:
        show("sift front matter parser", exc)


if __name__ == "__main__":
    main()
