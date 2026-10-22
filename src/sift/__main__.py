"""Run: python -m sift search | stats | bench."""

import sys
import time
from collections import Counter
from pathlib import Path

from sift.analysis import Pipeline, build_pipeline
from sift.corpus import iter_documents
from sift.document import Document
from sift.errors import QuerySyntaxError, SiftError
from sift.index import IndexWriter, InvertedIndex
from sift.log import setup_logging
from sift.query import parse
from sift.search import Searcher
from sift.snippet import render_plain
from sift.util import timed

CORPUS = Path("corpus/posts")
QUERIES = Path("bench/queries.txt")
USAGE = "usage: python -m sift search <query> | stats | bench"


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


def run_search(words: list[str]) -> None:
    """Print the top 10 documents for the query made of words.

    The words are joined with spaces back into one query string, so
    ``search '"device tree"'`` and ``search device tree`` both work.
    """
    query = " ".join(words)
    parse(query)  # fail fast: a typo must not cost an index build
    start = time.perf_counter()
    pipeline = build_pipeline()
    documents, index = load_index(CORPUS, pipeline)
    searcher = Searcher(index, pipeline=pipeline)
    built = time.perf_counter()
    result = searcher.search(query)
    for rank, hit in enumerate(result.hits, 1):
        print(f"{rank:>2}  {hit.score:7.3f}  {hit.path}")
        print(f"    {hit.title}")
        print(f"    {render_plain(hit.snippet)}")
    print(
        f"{result.total} hits in {len(documents)} files: "
        f"index built in {(built - start) * 1000:.1f} ms, "
        f"query took {result.took_ms:.3f} ms"
    )


def run_bench() -> None:
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


def run_stats() -> None:
    """Print document count, vocabulary size and the 20 top terms."""
    start = time.perf_counter()
    documents, index = load_index(CORPUS, build_pipeline())
    built = time.perf_counter()
    totals = Counter({term: sum(p.tf for p in index[term]) for term in index})
    print(f"documents: {len(documents)}")
    print(f"vocabulary: {len(index)}")
    for term, count in totals.most_common(20):
        print(f"{count:>7}  {term}")
    print(f"index built in {(built - start) * 1000:.1f} ms")


def dispatch(args: list[str]) -> None:
    """Run the subcommand named by args, or exit with the usage."""
    if args[:1] == ["search"] and len(args) > 1:
        run_search(args[1:])
    elif args == ["stats"]:
        run_stats()
    elif args == ["bench"]:
        run_bench()
    else:
        sys.exit(USAGE)


def main() -> None:
    """Run the command line and turn Sift errors into exit codes.

    A QuerySyntaxError prints the query and a caret line and exits 3.
    Any other SiftError, alone or inside an ExceptionGroup, prints
    ``error: ...`` and exits 1. The full contract arrives in ch11.
    """
    setup_logging()
    try:
        dispatch(sys.argv[1:])
    except QuerySyntaxError as error:
        print(error.render(), file=sys.stderr)
        sys.exit(3)
    except SiftError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    except ExceptionGroup as group:
        if group.subgroup(lambda e: not isinstance(e, SiftError)):
            raise
        print(f"error: {group.message}", file=sys.stderr)
        for error in group.exceptions:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
