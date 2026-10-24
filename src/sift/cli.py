"""The command line of Sift: ``sift <command>`` and ``python -m sift``.

Exit codes: 0 ok (also when a query has no hits), 2 usage error
(argparse), 3 malformed query, 4 index missing, 1 any other
SiftError.

``sift index`` writes the index directory (``.sift`` by default, the
``[index] path`` of ``sift.toml``) and the other commands read it:
``sift search`` maps the segment file instead of rebuilding the index
in memory, and logs the query in ``sift.db`` unless run with
``--no-log``; ``sift stats`` lists the last ten logged queries.
SIFT_INDEX names another index directory.

The storage modules (and with them SQLAlchemy) are imported by the
commands that use them, so ``sift --version`` and ``sift bench index``
start without that cost and run on an interpreter that lacks it.
"""

import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from sift import __version__
from sift.analysis import Pipeline, build_pipeline
from sift.config import Config, load_config
from sift.corpus import iter_documents
from sift.document import Document
from sift.errors import (
    ConfigError,
    IndexMissingError,
    QuerySyntaxError,
    SiftError,
)
from sift.index import IndexWriter, InvertedIndex
from sift.log import setup_logging
from sift.parallel import (
    MODES,
    Mode,
    Timing,
    bench_index,
    gil_enabled,
    read_items,
    replicate,
)
from sift.query import parse
from sift.search import Searcher
from sift.snippet import render_plain
from sift.util import timed

if TYPE_CHECKING:
    from sift.storage.store import SegmentIndex

CORPUS = Path("corpus/posts")
QUERIES = Path("bench/queries.txt")


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


def positive_int(text: str) -> int:
    """Convert text to an int greater than zero, for argparse."""
    try:
        number = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid int value: {text!r}"
        ) from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {text!r}")
    return number


def limit_arg(text: str) -> int:
    """Convert text to a hit count, by the rules of Config.limit."""
    try:
        number = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid int value: {text!r}"
        ) from None
    try:
        return Config.limit.validate(number)
    except ConfigError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def doc_id_arg(text: str) -> int:
    """Convert text to a document id (an int, zero or more)."""
    try:
        number = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid document id: {text!r}"
        ) from None
    if number < 0:
        raise argparse.ArgumentTypeError(f"negative document id: {text!r}")
    return number


def jobs_list_arg(text: str) -> list[int]:
    """Convert "1,2,4" to [1, 2, 4], without repeats, for argparse."""
    return list(dict.fromkeys(positive_int(part) for part in text.split(",")))


def modes_arg(text: str) -> list[Mode]:
    """Convert "process,thread" to a list of modes, for argparse."""
    modes: list[Mode] = []
    for part in text.split(","):
        for mode in MODES:
            if part == mode:
                modes.append(mode)
                break
        else:
            raise argparse.ArgumentTypeError(
                f"unknown mode {part!r}, use one of {', '.join(MODES)}"
            )
    return list(dict.fromkeys(modes))


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


def run_index(args: argparse.Namespace) -> None:
    """Build or update the index directory and print what changed."""
    from sift.storage.store import update_index

    config = load_config()
    corpus = args.corpus or config.corpus
    start = time.perf_counter()
    report = update_index(
        corpus,
        index_dir(config),
        config.pipeline,
        full=args.full,
        jobs=args.jobs,
        mode=args.mode,
    )
    took = (time.perf_counter() - start) * 1000
    mode = "full rebuild" if report.full else "incremental"
    print(f"documents: {report.documents}")
    print(f"vocabulary: {report.terms}")
    print(
        f"{mode}: parsed {report.parsed}, unchanged {report.unchanged}, "
        f"removed {report.removed}; segment {report.size} bytes; "
        f"took {took:.1f} ms"
    )


def run_stats(args: argparse.Namespace) -> None:
    """Print the stats of the index."""
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


def run_search(args: argparse.Namespace) -> None:
    """Print the best documents for the query."""
    from sift.storage.db import log_query
    from sift.storage.store import DB, open_index

    config = load_config()
    directory = index_dir(config)
    require_index(directory)
    query = read_query(args.query)
    parse(query)  # fail fast: a typo must not cost an index open
    start = time.perf_counter()
    with open_index(directory) as index:
        searcher = Searcher(
            index,
            k1=config.k1,
            b=config.b,
            pipeline=build_pipeline(index.pipeline_names),
        )
        opened = time.perf_counter()
        result = searcher.search(query, args.limit or config.limit)
        n_docs = index.n_docs
    if not args.no_log:
        try:
            log_query(directory / DB, query, result.total, result.took_ms)
        except SiftError:
            # the error text can hold the query: say only where
            print(
                f"sift: warning: query not logged, cannot write "
                f"{directory / DB}",
                file=sys.stderr,
            )
    if args.json:
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
    for rank, hit in enumerate(result.hits, 1):
        print(f"{rank:>2}  {hit.score:7.3f}  {hit.path}")
        print(f"    {hit.title}")
        print(f"    {render_plain(hit.snippet)}")
    print(
        f"{result.total} hits in {n_docs} files: "
        f"index opened in {(opened - start) * 1000:.1f} ms, "
        f"query took {result.took_ms:.3f} ms"
    )


def find_document(doc_id: int) -> Document:
    """Return the document with doc_id; raise SiftError if none."""
    from sift.storage.db import load_document
    from sift.storage.store import DB

    directory = index_dir(load_config())
    require_index(directory)
    doc = load_document(directory / DB, doc_id)
    if doc is None:
        raise SiftError(f"no document with id {doc_id}")
    return doc


def run_show(args: argparse.Namespace) -> None:
    """Print the metadata and the text of one document."""
    doc = find_document(args.doc_id)
    print(f"title: {doc.title}")
    print(f"path: {doc.path}")
    print(f"published: {doc.published.isoformat()}")
    print(f"tags: {', '.join(doc.tags)}")
    print(f"category: {doc.category or ''}")
    print(f"series: {doc.series or ''}")
    print()
    print(doc.body)


def run_open(args: argparse.Namespace) -> None:
    """Open one document in $EDITOR (default vi)."""
    doc = find_document(args.doc_id)
    editor = os.environ.get("EDITOR", "vi")
    try:
        done = subprocess.run([*shlex.split(editor), str(doc.path)])
    except FileNotFoundError:
        raise SiftError(f"cannot run editor {editor!r}") from None
    if done.returncode != 0:
        raise SiftError(f"{editor} exited with status {done.returncode}")


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


def run_bench_index(args: argparse.Namespace) -> None:
    """Time index_items on the corpus repeated args.repeat times.

    The corpus is read once, copied args.repeat times in memory with
    the doc_ids renumbered, and indexed for every jobs and mode. The
    table shows the best of args.rounds runs in seconds and the
    speedup over the serial build; jobs=1 is that build in every mode.
    """
    config = load_config()
    check_corpus(config.corpus)
    base = read_items(config.corpus)
    items = replicate(base, args.repeat)
    gil = "enabled" if gil_enabled() else "disabled"
    print(
        f"corpus: {len(base)} files x {args.repeat} = {len(items)} "
        f"documents, pipeline {','.join(config.pipeline)}"
    )
    print(
        f"python {platform.python_version()}, GIL {gil}, "
        f"{os.cpu_count()} CPUs, best of {args.rounds} rounds"
    )
    serial, timings = bench_index(
        items,
        config.pipeline,
        args.jobs,
        args.mode,
        rounds=args.rounds,
    )
    print_bench_table(serial, timings, args.mode)


def run_bench_search(args: argparse.Namespace) -> None:
    """Run bench/queries.txt: open the index once, time each query."""
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


def build_parser() -> argparse.ArgumentParser:
    """Return the parser of the whole command line."""
    parser = argparse.ArgumentParser(
        prog="sift",
        description="Search the Markdown posts of a blog.",
        epilog=(
            "exit codes: 0 ok, 2 usage, 3 bad query, 4 no index, 1 other error"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"sift {__version__}"
    )
    commands = parser.add_subparsers(
        title="commands", dest="command", metavar="COMMAND", required=True
    )

    cmd = commands.add_parser(
        "index", help="build or update the index and print its stats"
    )
    cmd.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="directory of Markdown posts (default: [index] corpus)",
    )
    cmd.add_argument(
        "--full",
        action="store_true",
        help="rebuild from scratch instead of updating",
    )
    cmd.add_argument(
        "--jobs",
        type=positive_int,
        default=1,
        help="workers that parse and analyze files (default: 1)",
    )
    cmd.add_argument(
        "--mode",
        choices=MODES,
        default="process",
        help="kind of worker when --jobs > 1 (default: %(default)s)",
    )
    cmd.set_defaults(func=run_index)

    cmd = commands.add_parser("search", help="search the index")
    cmd.add_argument(
        "query", nargs="+", help="query words; a lone - reads stdin"
    )
    cmd.add_argument(
        "--limit",
        type=limit_arg,
        default=None,
        help="most hits to print (default: [search] limit of sift.toml)",
    )
    cmd.add_argument("--json", action="store_true", help="print JSON")
    cmd.add_argument(
        "--no-log",
        action="store_true",
        help="do not log the query in sift.db",
    )
    cmd.set_defaults(func=run_search)

    cmd = commands.add_parser("show", help="print one document")
    cmd.add_argument("doc_id", type=doc_id_arg, metavar="DOC_ID")
    cmd.set_defaults(func=run_show)

    cmd = commands.add_parser("stats", help="print index statistics")
    cmd.set_defaults(func=run_stats)

    cmd = commands.add_parser("open", help="open a document in $EDITOR")
    cmd.add_argument("doc_id", type=doc_id_arg, metavar="DOC_ID")
    cmd.set_defaults(func=run_open)

    cmd = commands.add_parser("bench", help="time indexing or searching")
    kinds = cmd.add_subparsers(
        title="benchmarks", dest="kind", metavar="KIND", required=True
    )
    sub = kinds.add_parser(
        "index", help="time parallel indexing: a table of jobs x mode"
    )
    sub.add_argument(
        "--repeat",
        type=positive_int,
        default=8,
        help="copies of the corpus to index (default: %(default)s)",
    )
    sub.add_argument(
        "--jobs",
        type=jobs_list_arg,
        default="1,2,4,8",
        help="comma-separated worker counts (default: %(default)s)",
    )
    sub.add_argument(
        "--mode",
        type=modes_arg,
        default="process,thread,interp",
        help="comma-separated modes (default: %(default)s)",
    )
    sub.add_argument(
        "--rounds",
        type=positive_int,
        default=3,
        help="runs per cell, the best is kept (default: %(default)s)",
    )
    sub.set_defaults(func=run_bench_index)
    sub = kinds.add_parser("search", help="run bench/queries.txt")
    sub.set_defaults(func=run_bench_search)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the command line and turn Sift errors into exit codes.

    argv defaults to sys.argv[1:]. A usage error exits 2 (argparse).
    A QuerySyntaxError prints the query and a caret line and exits 3.
    IndexMissingError prints ``sift: ...`` and exits 4. Any other
    SiftError, alone or inside an ExceptionGroup, prints
    ``error: ...`` and exits 1. Ctrl-C prints ``interrupted`` and exits
    130 (128 + SIGINT). Success returns None.
    """
    setup_logging()
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except QuerySyntaxError as error:
        print(error.render(), file=sys.stderr)
        sys.exit(3)
    except IndexMissingError as error:
        print(f"sift: {error}", file=sys.stderr)
        sys.exit(4)
    except SiftError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        sys.exit(130)
    except ExceptionGroup as group:
        _, other = group.split(SiftError)
        if other is not None:
            raise
        print(f"error: {group.message}", file=sys.stderr)
        for failure in group.exceptions:
            print(f"  {failure}", file=sys.stderr)
        sys.exit(1)
