"""Custom exceptions: the SiftError hierarchy and how it behaves."""

import pickle
from pathlib import Path

from sift.errors import (
    ConfigError,
    FrontMatterError,
    IndexCorruptError,
    IndexMissingError,
    QuerySyntaxError,
    SiftError,
)


class BadError(Exception):
    """An exception whose __init__ forgets to pass every argument."""

    def __init__(self, message: str, detail: str) -> None:
        """Keep detail, but give only message to Exception."""
        super().__init__(message)  # BAD: args lacks detail
        self.detail = detail


def main() -> None:
    """Show the hierarchy, the attributes and a pickling pitfall."""
    for cls in (
        QuerySyntaxError,
        FrontMatterError,
        ConfigError,
        IndexMissingError,
        IndexCorruptError,
    ):
        print(f"{cls.__name__:18} mro: {[c.__name__ for c in cls.__mro__]}")
    print("SiftError is an Exception:", issubclass(SiftError, Exception))
    print(
        "SiftError is not a ValueError:", not issubclass(SiftError, ValueError)
    )

    errors: list[SiftError] = [
        QuerySyntaxError("expected ')'", "(rust", 5),
        FrontMatterError(Path("post.md"), 3, "duplicate key 'title'"),
        ConfigError("unknown tokenizer 'x'"),
    ]
    for error in errors:
        try:
            raise error
        except SiftError as caught:
            print(f"caught {type(caught).__name__}: {caught}")
            print(f"  args = {caught.args!r}")

    original = QuerySyntaxError("expected ')'", "(rust", 5)
    copy = pickle.loads(pickle.dumps(original))
    print("pickle round trip:", copy.message, copy.query, copy.position)

    try:
        pickle.loads(pickle.dumps(BadError("boom", "details")))
    except TypeError as exc:
        # error: TypeError: BadError.__init__() missing 1 required
        # positional argument: 'detail'
        print("BadError pickle fails:", exc)


if __name__ == "__main__":
    main()
