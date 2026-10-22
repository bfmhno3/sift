"""Context managers: the protocol, contextlib and the stdlib set."""

import contextlib
import io
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType


class Trace:
    """A class-based context manager that prints each step."""

    def __init__(self, name: str, *, swallow: bool = False) -> None:
        """Name the block; swallow decides what __exit__ returns."""
        self.name = name
        self.swallow = swallow

    def __enter__(self) -> str:
        """Print and return the value bound by ``as``."""
        print(f"  {self.name}: __enter__")
        return f"<{self.name}>"

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """Print what arrived; a true return value suppresses it."""
        print(f"  {self.name}: __exit__ got {exc_type}, {exc!r}")
        return self.swallow


@contextlib.contextmanager
def announce(name: str) -> Iterator[str]:
    """Generator-based context manager with try/finally."""
    print(f"  {name}: before yield")
    try:
        yield name.upper()
    finally:
        print(f"  {name}: after yield (finally)")


class Resource:
    """Something with a close() method, for contextlib.closing."""

    def close(self) -> None:
        """Print that the resource is closed."""
        print("  Resource.close() called")


def main() -> None:
    """Walk through the with statement and contextlib."""
    print("-- normal exit")
    with Trace("a") as value:
        print("  body, as =", value)

    print("-- exception, __exit__ returns False")
    try:
        with Trace("b"):
            raise ValueError("boom")
    except ValueError as exc:
        print("  caught outside:", exc)

    print("-- exception, __exit__ returns True")
    with Trace("c", swallow=True):
        raise ValueError("swallowed")
    print("  execution continues after the with")

    print("-- contextlib.contextmanager")
    with announce("gen") as upper:
        print("  body, as =", upper)
    try:
        with announce("gen2"):
            raise KeyError("x")
    except KeyError:
        print("  the exception passed through the generator")

    print("-- two managers in one with (exit in reverse order)")
    with Trace("outer"), Trace("inner"):
        print("  body")

    print("-- ExitStack")
    with contextlib.ExitStack() as stack:
        for name in ("one", "two", "three"):
            stack.enter_context(Trace(name))
        stack.callback(print, "  callback runs first on the way out")
        print("  body")

    print("-- suppress")
    with contextlib.suppress(FileNotFoundError):
        Path("/no/such/file").read_text()
    print("  FileNotFoundError ignored")

    print("-- closing")
    with contextlib.closing(Resource()):
        print("  body")

    print("-- redirect_stdout")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print("this goes to the buffer")
    print("  captured:", repr(buffer.getvalue()))

    print("-- redirect_stderr")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        print("to stderr", file=sys.stderr)
    print("  captured:", repr(err.getvalue()))

    print("-- contextlib.chdir")
    before = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        inside = Path.cwd() == Path(tmp).resolve()
        print("  cwd is the temp dir:", inside)
    print("  cwd restored:", Path.cwd() == before)

    print("-- files are context managers too")
    with open(os.devnull, "w", encoding="utf-8") as f:
        print("  closed inside:", f.closed)
    print("  closed after:", f.closed)

    print("-- nullcontext")
    with contextlib.nullcontext("placeholder") as value:
        print("  value:", value)


if __name__ == "__main__":
    main()
