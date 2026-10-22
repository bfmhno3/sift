"""The command line of Sift: ``sift <command>`` and ``python -m sift``.

Exit codes: 0 ok (also when a query has no hits), 2 usage error
(argparse), 3 malformed query, 4 index missing, 1 any other
SiftError.

SIFT_INDEX names the directory of the persisted index. The index is
only persisted from chapter 12, so for now the variable has one
effect: when it is set, the commands that read the index (search,
show, stats, open) fail with exit code 4 unless that directory
exists. When it is not set they build the index in memory, as
before.
"""

import argparse
import json
import os
import shlex
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from sift import __version__
from sift.analysis import Pipeline, build_pipeline
from sift.corpus import iter_documents
from sift.document import Document
from sift.errors import (
    IndexMissingError,
    QuerySyntaxError,
    SiftError,
)
from sift.index import IndexWriter, InvertedIndex
from sift.log import setup_logging
from sift.query import parse
from sift.search import Searcher
from sift.snippet import render_plain
from sift.util import timed

CORPUS = Path("corpus/posts")
QUERIES = Path("bench/queries.txt")


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
    documents: list[Document] = []
    index = InvertedIndex()
    with IndexWriter(index, pipeline) as writer:
        for doc in iter_documents(root, keep_going=keep_going):
            documents.append(doc)
            writer.add(doc)
    return documents, index


def index_dir() -> Path | None:
    """Return the directory named by SIFT_INDEX, or None if unset."""
    value = os.environ.get("SIFT_INDEX")
    return Path(value) if value else None


def check_index_dir() -> None:
    """Raise IndexMissingError if SIFT_INDEX names a missing directory.

    With SIFT_INDEX unset there is nothing to check: until chapter 12
    the index lives in memory and is built on demand.
    """
    path = index_dir()
    if path is not None and not path.is_dir():
        raise IndexMissingError(f"no index at {path}, run 'sift index' first")


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


def print_stats(documents: list[Document], index: InvertedIndex) -> None:
    """Print document count, vocabulary size and the 20 top terms."""
    totals = Counter({term: sum(p.tf for p in index[term]) for term in index})
    print(f"documents: {len(documents)}")
    print(f"vocabulary: {len(index)}")
    for term, count in totals.most_common(20):
        print(f"{count:>7}  {term}")


def report(root: Path) -> None:
    """Build the index of root in memory and print its stats."""
    start = time.perf_counter()
    documents, index = load_index(root, build_pipeline())
    built = time.perf_counter()
    print_stats(documents, index)
    print(f"index built in {(built - start) * 1000:.1f} ms")


def run_index(args: argparse.Namespace) -> None:
    """Build the index and print its stats."""
    report(args.corpus)


def run_stats(args: argparse.Namespace) -> None:
    """Print the stats of the index."""
    check_index_dir()
    report(CORPUS)


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
    check_index_dir()
    query = read_query(args.query)
    parse(query)  # fail fast: a typo must not cost an index build
    start = time.perf_counter()
    pipeline = build_pipeline()
    documents, index = load_index(CORPUS, pipeline)
    searcher = Searcher(index, pipeline=pipeline)
    built = time.perf_counter()
    result = searcher.search(query, args.limit)
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
        f"{result.total} hits in {len(documents)} files: "
        f"index built in {(built - start) * 1000:.1f} ms, "
        f"query took {result.took_ms:.3f} ms"
    )


def find_document(doc_id: int) -> Document:
    """Return the document with doc_id; raise SiftError if none."""
    check_index_dir()
    for doc in iter_documents(CORPUS):
        if doc.doc_id == doc_id:
            return doc
    raise SiftError(f"no document with id {doc_id}")


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


def run_bench_index(args: argparse.Namespace) -> None:
    """Time args.repeat in-memory index builds."""
    seconds = []
    for _ in range(args.repeat):
        start = time.perf_counter()
        load_index(CORPUS, build_pipeline())
        seconds.append(time.perf_counter() - start)
    print(
        f"{args.repeat} builds: "
        f"min {min(seconds) * 1000:.1f} ms, "
        f"median {statistics.median(seconds) * 1000:.1f} ms"
    )


def run_bench_search(args: argparse.Namespace) -> None:
    """Run bench/queries.txt: build the index once, time each query."""
    pipeline = build_pipeline()
    _, index = load_index(CORPUS, pipeline)
    searcher = Searcher(index, pipeline=pipeline)
    queries = QUERIES.read_text(encoding="utf-8").splitlines()
    timings = []
    for query in filter(None, queries):
        start = time.perf_counter()
        result = searcher.search(query)
        timings.append((query, result.total, time.perf_counter() - start))
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
        "index", help="build the index and print its stats"
    )
    cmd.add_argument(
        "--corpus",
        type=Path,
        default=CORPUS,
        help="directory of Markdown posts (default: %(default)s)",
    )
    cmd.set_defaults(func=run_index)

    cmd = commands.add_parser("search", help="search the index")
    cmd.add_argument(
        "query", nargs="+", help="query words; a lone - reads stdin"
    )
    cmd.add_argument(
        "--limit",
        type=positive_int,
        default=10,
        help="most hits to print (default: %(default)s)",
    )
    cmd.add_argument("--json", action="store_true", help="print JSON")
    cmd.add_argument(
        "--no-log",
        action="store_true",
        help="do not log the query (there is no query log yet)",
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
    sub = kinds.add_parser("index", help="time in-memory index builds")
    sub.add_argument(
        "--repeat",
        type=positive_int,
        default=8,
        help="number of builds (default: %(default)s)",
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
    ``error: ...`` and exits 1. Success returns None.
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
    except ExceptionGroup as group:
        _, other = group.split(SiftError)
        if other is not None:
            raise
        print(f"error: {group.message}", file=sys.stderr)
        for error in group.exceptions:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)
