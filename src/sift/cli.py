"""The command line of Sift: ``sift <command>`` and ``python -m sift``.

Built with typer: the type hints of the ``run_*`` functions are the
options and arguments, ``Annotated[..., typer.Option(...)]`` adds the
help and the checks.

Exit codes: 0 ok (also when a query has no hits), 2 usage error
(click, the library under typer), 3 malformed query, 4 index missing,
1 any other SiftError. The mapping lives in ``SiftGroup.invoke``, so
``sift`` and the typer test runner see the same codes.

``sift index`` writes the index directory (``.sift`` by default, the
``[index] path`` of ``sift.toml``) and the other commands read it:
``sift search`` maps the segment file instead of rebuilding the index
in memory, and logs the query in ``sift.db`` unless run with
``--no-log``; ``sift stats`` lists the last ten logged queries.
SIFT_INDEX names another index directory. ``sift serve`` serves the
index over HTTP with FastAPI on uvicorn (``sift.server.app``, the
``web`` extra); ``sift serve --raw`` uses the hand-written asyncio
server of ``sift.server.raw`` instead. ``sift gui`` opens the search
window (``sift.gui.tk_app``, tkinter, the ``gui`` extra).

Output goes through rich (``sift.render``) only on a terminal; in a
pipe, with ``--json`` or with NO_COLOR set it is plain text: the
output of the commands is the text of chapter 18, and the help and
the usage errors are click's plain text, without boxes.

``--debug`` logs at DEBUG level and prints uncaught exceptions, and
the errors below, as rich tracebacks.

The storage modules (and with them SQLAlchemy), asyncio and rich are
imported by the commands that use them, so ``sift --version`` and
``sift bench index`` start without that cost and run on an
interpreter that lacks SQLAlchemy.
"""

import os
import sys
import time
from collections import Counter
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn

import click
import typer
from typer.core import TyperGroup

from sift import render
from sift.errors import (
    ConfigError,
    IndexMissingError,
    QuerySyntaxError,
    SiftError,
)
from sift.log import setup_logging
from sift.util import timed

if TYPE_CHECKING:
    from sift.analysis import Pipeline
    from sift.config import Config
    from sift.document import Document
    from sift.index import InvertedIndex
    from sift.parallel import Mode, Timing
    from sift.search import Searcher
    from sift.storage.store import SegmentIndex

CORPUS = Path("corpus/posts")
QUERIES = Path("bench/queries.txt")
DEBUG_KEY = "sift.debug"
MODE_NAMES = "process, thread or interp"


class SiftGroup(TyperGroup):
    """The root command group: Sift errors become exit codes.

    A usage error (bad option, bad value) is raised by click while it
    parses the arguments and leaves through typer, which prints it and
    exits 2. The errors of Sift are caught here, around the whole
    invocation, because they come out of the command functions.
    """

    def invoke(self, ctx: click.Context) -> object:
        """Run the command; print a Sift error, exit with its code."""
        try:
            return super().invoke(ctx)
        except QuerySyntaxError as error:
            fail(ctx, error.render(), 3)
        except IndexMissingError as error:
            fail(ctx, f"sift: {error}", 4)
        except SiftError as error:
            fail(ctx, f"error: {error}", 1)
        except KeyboardInterrupt:
            fail(ctx, "interrupted", 130, trace=False)
        except ExceptionGroup as group:
            _, other = group.split(SiftError)
            if other is not None:
                raise
            lines = [f"error: {group.message}"]
            lines += [f"  {failure}" for failure in group.exceptions]
            fail(ctx, "\n".join(lines), 1)


def fail(
    ctx: click.Context, message: str, code: int, *, trace: bool = True
) -> NoReturn:
    """Print message on stderr and exit with code.

    Call it from an ``except`` block. With --debug the exception
    being handled is first printed as a rich traceback.
    """
    if trace and ctx.meta.get(DEBUG_KEY):
        render.print_traceback()
    print(message, file=sys.stderr)
    ctx.exit(code)


def markup_mode() -> Literal["rich"] | None:
    """Return "rich" if help and usage errors may be drawn, else None.

    None makes typer print click's plain text. Both streams must be
    terminals: help goes to stdout, usage errors to stderr, and
    ``2>&1 | cat`` must give no boxes either.
    """
    if render.wants_rich(sys.stdout) and render.wants_rich(sys.stderr):
        return "rich"
    return None


app = typer.Typer(
    cls=SiftGroup,
    rich_markup_mode=markup_mode(),
    name="sift",
    help="Search the Markdown posts of a blog.",
    epilog=(
        "Exit codes: 0 ok, 2 usage, 3 bad query, 4 no index, 1 other error."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
bench_app = typer.Typer(
    help="Time indexing or searching.",
    no_args_is_help=True,
    rich_markup_mode=markup_mode(),
)
app.add_typer(bench_app, name="bench")


def show_version(value: bool) -> None:
    """Print the version and exit, for the eager ``--version``."""
    if value:
        from sift import __version__

        typer.echo(f"sift {__version__}")
        raise typer.Exit


@app.callback()
def run_root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=show_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Log at DEBUG level and print tracebacks with rich.",
        ),
    ] = False,
) -> None:
    """Set up logging, and the rich traceback with --debug."""
    ctx.meta[DEBUG_KEY] = debug
    setup_logging(
        "DEBUG" if debug else "WARNING", rich=render.wants_rich(sys.stderr)
    )
    if debug:
        render.install_traceback()


def check_corpus(root: Path) -> None:
    """Raise SiftError if root is not a directory."""
    if not root.is_dir():
        raise SiftError(f"no corpus at {root}")


@timed
def load_index(
    root: Path,
    pipeline: Pipeline | None = None,
    *,
    keep_going: bool = False,
) -> tuple[list[Document], InvertedIndex]:
    """Read, analyze and index every Markdown file under root.

    pipeline defaults to build_pipeline().

    The doc_id of a document is its position in the sorted path list.
    Files with a malformed front matter are collected: without
    keep_going they raise one ExceptionGroup after the last file and
    no index is returned, with keep_going they are logged as warnings
    and skipped (their doc_ids stay unused).
    """
    from sift.corpus import iter_documents
    from sift.index import IndexWriter, InvertedIndex

    check_corpus(root)
    documents: list[Document] = []
    index = InvertedIndex()
    with IndexWriter(index, pipeline) as writer:
        for doc in iter_documents(root, keep_going=keep_going):
            documents.append(doc)
            writer.add(doc)
    return documents, index


def index_dir(config: Config) -> Path:
    """Return the index directory: SIFT_INDEX, else the config path."""
    value = os.environ.get("SIFT_INDEX")
    return Path(value) if value else config.index_path


def require_index(directory: Path) -> None:
    """Raise IndexMissingError if directory holds no segment."""
    from sift.storage.store import SEGMENT

    if not (directory / SEGMENT).is_file():
        raise IndexMissingError(
            f"no index at {directory}, run 'sift index' first"
        )


def int_arg(text: str) -> int:
    """Convert text to an int; raise BadParameter if it is not one."""
    try:
        return int(text)
    except ValueError:
        raise typer.BadParameter(f"invalid int value: {text!r}") from None


def positive_int(text: str) -> int:
    """Convert text to an int greater than zero."""
    number = int_arg(text)
    if number < 1:
        raise typer.BadParameter(f"must be at least 1: {text!r}")
    return number


def limit_arg(text: str) -> int:
    """Convert text to a hit count, by the rules of Config.limit."""
    from sift.config import Config

    try:
        return Config.limit.validate(int_arg(text))
    except ConfigError as error:
        raise typer.BadParameter(str(error)) from None


def jobs_list_arg(text: str) -> list[int]:
    """Convert "1,2,4" to [1, 2, 4], without repeats."""
    try:
        numbers = (positive_int(part) for part in text.split(","))
        return list(dict.fromkeys(numbers))
    except typer.BadParameter as error:
        raise typer.BadParameter(
            error.message, param_hint="'--jobs'"
        ) from None


def mode_arg(text: str) -> Mode:
    """Convert text to one mode, for ``--mode``."""
    from sift.parallel import MODES

    for mode in MODES:
        if text == mode:
            return mode
    raise typer.BadParameter(
        f"unknown mode {text!r}, use one of {', '.join(MODES)}",
        param_hint="'--mode'",
    )


def modes_arg(text: str) -> list[Mode]:
    """Convert "process,thread" to a list of modes, without repeats."""
    return list(dict.fromkeys(mode_arg(part) for part in text.split(",")))


def port_arg(text: str) -> int:
    """Convert text to a TCP port, 0 to 65535."""
    number = int_arg(text)
    if not 0 <= number <= 65535:
        raise typer.BadParameter(f"port out of range: {text!r}")
    return number


def print_stats(index: SegmentIndex) -> None:
    """Print document count, vocabulary size, size and 20 top terms."""
    totals = Counter(
        {
            term: sum(p.tf for p in plist)
            for term, plist in index.segment.iter_postings()
        }
    )
    print(f"documents: {index.n_docs}")
    print(f"vocabulary: {len(index)}")
    print(f"segment: {index.segment.size} bytes")
    for term, count in totals.most_common(20):
        print(f"{count:>7}  {term}")


def print_recent_queries(directory: Path, limit: int = 10) -> None:
    """Print the last limit logged queries, newest first."""
    from sift.storage.db import recent_queries
    from sift.storage.store import DB

    rows = recent_queries(directory / DB, limit)
    if not rows:
        print("no queries logged")
        return
    print(f"last {len(rows)} queries:")
    for row in rows:
        stamp = row.at.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{stamp} UTC  {row.total:>5} hits  "
            f"{row.took_ms:>8.3f} ms  {row.query}"
        )


@app.command("index", help="Build or update the index and print its stats.")
def run_index(
    corpus: Annotated[
        Path | None,
        typer.Option(
            help="Directory of Markdown posts "
            "(default: the corpus setting of sift.toml).",
        ),
    ] = None,
    full: Annotated[
        bool,
        typer.Option(
            "--full", help="Rebuild from scratch instead of updating."
        ),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option(
            parser=positive_int,
            metavar="N",
            help="Workers that parse and analyze files.",
        ),
    ] = 1,
    mode: Annotated[
        str,
        typer.Option(
            metavar="MODE",
            help=f"Kind of worker when --jobs > 1: {MODE_NAMES}.",
        ),
    ] = "process",
) -> None:
    """Build or update the index directory and print what changed."""
    from sift.config import load_config
    from sift.storage.store import update_index

    worker = mode_arg(mode)
    config = load_config()
    start = time.perf_counter()
    with render.index_progress() as progress:
        report = update_index(
            corpus or config.corpus,
            index_dir(config),
            config.pipeline,
            full=full,
            jobs=jobs,
            mode=worker,
            progress=progress,
        )
    took = (time.perf_counter() - start) * 1000
    kind = "full rebuild" if report.full else "incremental"
    print(f"documents: {report.documents}")
    print(f"vocabulary: {report.terms}")
    print(
        f"{kind}: parsed {report.parsed}, unchanged {report.unchanged}, "
        f"removed {report.removed}; segment {report.size} bytes; "
        f"took {took:.1f} ms"
    )


@app.command("stats", help="Print index statistics.")
def run_stats() -> None:
    """Print the stats of the index."""
    from sift.config import load_config
    from sift.storage.store import open_index

    directory = index_dir(load_config())
    with open_index(directory) as index:
        print_stats(index)
    print_recent_queries(directory)


def read_query(words: list[str]) -> str:
    """Join words into one query; a lone ``-`` reads a line of stdin.

    The words are joined with spaces, so ``search '"device tree"'``
    and ``search device tree`` both work.
    """
    if words == ["-"]:
        return sys.stdin.readline().rstrip("\n")
    return " ".join(words)


@app.command("search", help="Search the index.")
def run_search(
    query: Annotated[
        list[str],
        typer.Argument(
            show_default=False,
            help="Query words; a lone - reads stdin.",
        ),
    ],
    limit: Annotated[
        int | None,
        typer.Option(
            parser=limit_arg,
            metavar="N",
            help="Most hits to print "
            "(default: the search limit of sift.toml).",
        ),
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print JSON.")
    ] = False,
    no_log: Annotated[
        bool,
        typer.Option("--no-log", help="Do not log the query in sift.db."),
    ] = False,
) -> None:
    """Print the best documents for the query."""
    import json

    from sift.analysis import build_pipeline
    from sift.config import load_config
    from sift.query import parse
    from sift.search import Searcher
    from sift.snippet import render_plain
    from sift.storage.db import log_query
    from sift.storage.store import DB, open_index

    config = load_config()
    directory = index_dir(config)
    require_index(directory)
    text = read_query(query)
    parse(text)  # fail fast: a typo must not cost an index open
    start = time.perf_counter()
    with open_index(directory) as index:
        searcher = Searcher(
            index,
            k1=config.k1,
            b=config.b,
            pipeline=build_pipeline(index.pipeline_names),
        )
        opened = time.perf_counter()
        result = searcher.search(text, limit or config.limit)
        n_docs = index.n_docs
    if not no_log:
        try:
            log_query(directory / DB, text, result.total, result.took_ms)
        except SiftError:
            # the error text can hold the query: say only where
            print(
                f"sift: warning: query not logged, cannot write "
                f"{directory / DB}",
                file=sys.stderr,
            )
    if as_json:
        payload = {
            "query": result.query,
            "total": result.total,
            "took_ms": result.took_ms,
            "hits": [
                {
                    "doc_id": hit.doc_id,
                    "title": hit.title,
                    "path": str(hit.path),
                    "score": hit.score,
                    "snippet": render_plain(hit.snippet),
                }
                for hit in result.hits
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return
    render.print_hits(
        result,
        n_docs,
        (opened - start) * 1000,
        render.stdout_console(),
    )


def find_document(doc_id: int) -> Document:
    """Return the document with doc_id; raise SiftError if none."""
    from sift.config import load_config
    from sift.storage.db import load_document
    from sift.storage.store import DB

    directory = index_dir(load_config())
    require_index(directory)
    doc = load_document(directory / DB, doc_id)
    if doc is None:
        raise SiftError(f"no document with id {doc_id}")
    return doc


DocId = Annotated[
    int, typer.Argument(min=0, metavar="DOC_ID", help="Document id.")
]


@app.command("show", help="Print one document.")
def run_show(doc_id: DocId) -> None:
    """Print the metadata and the text of one document."""
    doc = find_document(doc_id)
    print(f"title: {doc.title}")
    print(f"path: {doc.path}")
    print(f"published: {doc.published.isoformat()}")
    print(f"tags: {', '.join(doc.tags)}")
    print(f"category: {doc.category or ''}")
    print(f"series: {doc.series or ''}")
    print()
    print(doc.body)


@app.command("open", help="Open a document in $EDITOR.")
def run_open(doc_id: DocId) -> None:
    """Open one document in $EDITOR (default vi)."""
    import shlex
    import subprocess

    doc = find_document(doc_id)
    editor = os.environ.get("EDITOR", "vi")
    try:
        done = subprocess.run([*shlex.split(editor), str(doc.path)])
    except FileNotFoundError:
        raise SiftError(f"cannot run editor {editor!r}") from None
    if done.returncode != 0:
        raise SiftError(f"{editor} exited with status {done.returncode}")


@contextmanager
def searching(directory: Path, config: Config) -> Generator[Searcher]:
    """Open the index in directory and yield a Searcher over it."""
    from sift.analysis import build_pipeline
    from sift.search import Searcher
    from sift.storage.store import open_index

    with open_index(directory) as index:
        yield Searcher(
            index,
            k1=config.k1,
            b=config.b,
            pipeline=build_pipeline(index.pipeline_names),
        )


@app.command("serve", help="Serve search over HTTP.")
def run_serve(
    ctx: typer.Context,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Use the hand-written asyncio server of chapter 17 "
            "instead of FastAPI on uvicorn.",
        ),
    ] = False,
    host: Annotated[
        str,
        typer.Option(
            help="Address to listen on; there is no authentication, so "
            "a non-loopback address exposes the index.",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            parser=port_arg,
            metavar="PORT",
            help="Port to listen on, 0 for any free one.",
        ),
    ] = 8000,
    max_pending: Annotated[
        int,
        typer.Option(
            parser=positive_int,
            metavar="N",
            help="Searches running or waiting before the next one gets 503.",
        ),
    ] = 32,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Do not log one line per request."),
    ] = False,
) -> None:
    """Serve /search, /docs/<id> and /health until SIGTERM or Ctrl-C.

    FastAPI on uvicorn, or with --raw the hand-written server. Raise
    IndexMissingError (exit 4) if there is no index and SiftError
    (exit 1) if the address cannot be bound or FastAPI is not
    installed. The URL is printed on stdout once the socket listens.
    """
    import asyncio

    from sift.config import load_config

    config = load_config()
    directory = index_dir(config)
    require_index(directory)
    if ctx.meta.get(DEBUG_KEY):
        level = "DEBUG"
    else:
        level = "WARNING" if quiet else "INFO"
    setup_logging(level, rich=render.wants_rich(sys.stderr))
    announce = print_flushed
    if raw:
        from sift.server.raw import serve as serve_raw

        with searching(directory, config) as searcher:
            asyncio.run(
                serve_raw(
                    searcher,
                    config,
                    host,
                    port,
                    announce=announce,
                    max_pending=max_pending,
                )
            )
        return
    try:
        from sift.server.app import serve
    except ModuleNotFoundError as error:
        raise SiftError(
            f"sift serve needs the web extra ({error.name} is missing): "
            "pip install 'sift[web]', or use --raw"
        ) from None
    asyncio.run(
        serve(
            lambda: searching(directory, config),
            config,
            host,
            port,
            announce=announce,
            max_pending=max_pending,
            quiet=quiet,
        )
    )


@app.command("gui", help="Open the search window.")
def run_gui(
    tk: Annotated[
        bool,
        typer.Option(
            "--tk",
            help="Use the tkinter window (the only one until chapter 21).",
        ),
    ] = False,
) -> None:
    """Open the search window on the index and run it until it closes.

    Raise IndexMissingError (exit 4) if there is no index and
    SiftError (exit 1) if there is no display, the Python has no
    tkinter or the gui extra is not installed. ``--tk`` is the
    default and the only toolkit for now.
    """
    from sift.config import load_config

    config = load_config()
    directory = index_dir(config)
    require_index(directory)
    try:
        from sift.gui.controller import IndexBackend
        from sift.gui.tk_app import run
    except ModuleNotFoundError as error:
        if error.name in ("tkinter", "_tkinter"):
            raise SiftError(
                "sift gui needs tkinter, and this Python was built without it"
            ) from None
        raise SiftError(
            f"sift gui needs the gui extra ({error.name} is missing): "
            "pip install 'sift[gui]'"
        ) from None
    with searching(directory, config) as searcher:
        run(IndexBackend(searcher, config.limit))


def print_flushed(text: str) -> None:
    """Print text and flush: scripts wait for the line."""
    print(text, flush=True)


def print_bench_table(
    serial: float, timings: list[Timing], modes: Sequence[Mode]
) -> None:
    """Print seconds and speedup over serial for every jobs and mode."""
    print(f"{'jobs':>4}" + "".join(f"  {m:>17}" for m in modes))
    for jobs in dict.fromkeys(t.jobs for t in timings):
        row = {t.mode: t.seconds for t in timings if t.jobs == jobs}
        cells = "".join(
            f"  {row[m]:8.3f} s {serial / row[m]:5.2f}x" for m in modes
        )
        print(f"{jobs:>4}{cells}")


@bench_app.command(
    "index", help="Time parallel indexing: a table of jobs x mode."
)
def run_bench_index(
    repeat: Annotated[
        int,
        typer.Option(
            parser=positive_int,
            metavar="N",
            help="Copies of the corpus to index.",
        ),
    ] = 8,
    jobs: Annotated[
        str,
        typer.Option(metavar="LIST", help="Comma-separated worker counts."),
    ] = "1,2,4,8",
    mode: Annotated[
        str,
        typer.Option(
            metavar="LIST",
            help=f"Comma-separated modes: {MODE_NAMES}.",
        ),
    ] = "process,thread,interp",
    rounds: Annotated[
        int,
        typer.Option(
            parser=positive_int,
            metavar="N",
            help="Runs per cell, the best is kept.",
        ),
    ] = 3,
) -> None:
    """Time index_items on the corpus repeated ``repeat`` times.

    The corpus is read once, copied ``repeat`` times in memory with
    the doc_ids renumbered, and indexed for every jobs and mode. The
    table shows the best of ``rounds`` runs in seconds and the
    speedup over the serial build; jobs=1 is that build in every mode.
    """
    import platform

    from sift.config import load_config
    from sift.parallel import (
        bench_index,
        gil_enabled,
        read_items,
        replicate,
    )

    job_counts = jobs_list_arg(jobs)
    modes = modes_arg(mode)
    config = load_config()
    check_corpus(config.corpus)
    base = read_items(config.corpus)
    items = replicate(base, repeat)
    gil = "enabled" if gil_enabled() else "disabled"
    print(
        f"corpus: {len(base)} files x {repeat} = {len(items)} "
        f"documents, pipeline {','.join(config.pipeline)}"
    )
    print(
        f"python {platform.python_version()}, GIL {gil}, "
        f"{os.cpu_count()} CPUs, best of {rounds} rounds"
    )
    serial, timings = bench_index(
        items,
        config.pipeline,
        job_counts,
        modes,
        rounds=rounds,
    )
    print_bench_table(serial, timings, modes)


@bench_app.command("search", help="Run bench/queries.txt.")
def run_bench_search() -> None:
    """Run bench/queries.txt: open the index once, time each query."""
    from sift.analysis import build_pipeline
    from sift.config import load_config
    from sift.search import Searcher
    from sift.storage.store import open_index

    config = load_config()
    directory = index_dir(config)
    require_index(directory)
    queries = QUERIES.read_text(encoding="utf-8").splitlines()
    timings: list[tuple[str, int, float]] = []
    with open_index(directory) as index:
        searcher = Searcher(
            index,
            k1=config.k1,
            b=config.b,
            pipeline=build_pipeline(index.pipeline_names),
        )
        for query in filter(None, queries):
            start = time.perf_counter()
            result = searcher.search(query, config.limit)
            elapsed = time.perf_counter() - start
            timings.append((query, result.total, elapsed))
    total = sum(seconds for _, _, seconds in timings)
    for query, hits, seconds in timings:
        print(f"{seconds * 1000:8.2f} ms  {hits:>4} hits  {query}")
    print(f"{total * 1000:8.2f} ms  total for {len(timings)} queries")


def main(argv: Sequence[str] | None = None) -> None:
    """Run the command line; exit with the code of a failure.

    argv defaults to sys.argv[1:]. A usage error exits 2 (click).
    A QuerySyntaxError prints the query and a caret line and exits 3.
    IndexMissingError prints ``sift: ...`` and exits 4. Any other
    SiftError, alone or inside an ExceptionGroup, prints
    ``error: ...`` and exits 1. Ctrl-C prints ``interrupted`` and exits
    130 (128 + SIGINT). Success, ``--help`` and ``--version`` return
    None; typer would exit 0 for them, which is turned back here so
    that a program can call ``main`` as a function.
    """
    try:
        app(args=None if argv is None else list(argv), prog_name="sift")
    except SystemExit as stop:
        if stop.code:
            raise
