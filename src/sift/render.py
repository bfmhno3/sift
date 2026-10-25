"""Terminal output of the command line: rich on a terminal, else plain.

``wants_rich`` is the one decision. Output goes through rich only when
the stream is a terminal, ``NO_COLOR`` is unset or empty and ``TERM``
is not ``dumb``. Anywhere else (a pipe, a file, ``--json``, a test)
the commands print the plain text of chapter 18, byte for byte, so
scripts that parse it keep working.

This module imports only the standard library at the top: rich costs
tens of milliseconds, and ``sift --version`` or a piped ``sift stats``
must not pay for it. Every function that needs rich imports it when
it is called.
"""

import os
import sys
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    from sift.search import SearchResult

HIT_STYLE = "bold black on yellow"
Parts = Iterable[tuple[str, bool]]


def wants_rich(stream: TextIO) -> bool:
    """Return True if rich output suits stream.

    False for a stream that is not a terminal, when NO_COLOR is set
    to a non-empty value (https://no-color.org) and when TERM is
    ``dumb``.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return stream.isatty()


def stdout_console() -> Console | None:
    """Return a Console on stdout, or None if the output is plain."""
    if not wants_rich(sys.stdout):
        return None
    from rich.console import Console

    return Console()


def snippet_text(parts: Parts) -> Text:
    """Return the snippet as rich Text, the matched parts highlighted.

    The parts are the ``(text, matched)`` pairs of ``Hit.snippet``.
    The text is never parsed as console markup, so a ``[chain]`` in a
    post stays what it is.
    """
    from rich.text import Text

    text = Text()
    for piece, matched in parts:
        text.append(piece, style=HIT_STYLE if matched else None)
    return text


def hit_table(result: SearchResult) -> Table:
    """Return the hits as a table: rank, score, title, path, snippet."""
    from rich import box
    from rich.table import Table
    from rich.text import Text

    table = Table(box=box.ROUNDED, show_lines=True, expand=True)
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("score", justify="right", no_wrap=True)
    table.add_column("document", ratio=1, overflow="fold")
    for rank, hit in enumerate(result.hits, 1):
        cell = Text()
        cell.append(hit.title, style="bold cyan")
        cell.append("\n")
        cell.append(str(hit.path), style="dim")
        cell.append("\n")
        cell.append_text(snippet_text(hit.snippet))
        table.add_row(str(rank), f"{hit.score:.3f}", cell)
    return table


def summary_line(result: SearchResult, n_docs: int) -> str:
    """Return the hit count line without the timings."""
    return f"{result.total} hits in {n_docs} files"


def print_hits(
    result: SearchResult,
    n_docs: int,
    opened_ms: float,
    console: Console | None = None,
) -> None:
    """Print the hits of a search and the summary line.

    With a Console the hits are a rich table with the matches
    highlighted; with None they are the plain three lines per hit of
    chapter 18. The last line gives the open and query times.
    """
    footer = (
        f"{summary_line(result, n_docs)}: "
        f"index opened in {opened_ms:.1f} ms, "
        f"query took {result.took_ms:.3f} ms"
    )
    if console is None:
        from sift.snippet import render_plain

        for rank, hit in enumerate(result.hits, 1):
            print(f"{rank:>2}  {hit.score:7.3f}  {hit.path}")
            print(f"    {hit.title}")
            print(f"    {render_plain(hit.snippet)}")
        print(footer)
        return
    from rich.text import Text

    if result.hits:
        console.print(hit_table(result))
    console.print(Text(footer, style="dim"))


@contextmanager
def index_progress() -> Generator[Callable[[int, int], None] | None]:
    """Yield a ``progress(done, total)`` callback, or None.

    On a terminal stderr the callback draws a progress bar on stderr
    that disappears when the block ends; the bar is created by the
    first call, so a run that parses nothing draws nothing. Anywhere
    else the block gets None and nothing is drawn.
    """
    if not wants_rich(sys.stderr):
        yield None
        return
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
    )

    bar = Progress(
        TextColumn("indexing"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=Console(stderr=True),
        transient=True,
    )
    tasks: list[TaskID] = []

    def update(done: int, total: int) -> None:
        if not tasks:
            tasks.append(bar.add_task("index", total=total))
        bar.update(tasks[0], completed=done)

    with bar:
        yield update


def install_traceback() -> None:
    """Print uncaught exceptions as rich tracebacks (``--debug``)."""
    from rich.traceback import install

    install(show_locals=False)


def print_traceback() -> None:
    """Print the exception being handled as a rich traceback."""
    from rich.console import Console

    Console(stderr=True).print_exception(show_locals=False)
