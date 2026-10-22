"""Run: python -m sift search | stats | bench."""

import sys
import time
from collections import Counter
from pathlib import Path

from sift.analysis import Pipeline, build_pipeline
from sift.corpus import iter_documents
from sift.document import Document
from sift.index import InvertedIndex
from sift.query import QuerySyntaxError
from sift.search import Searcher
from sift.snippet import render_plain
from sift.util import timed

CORPUS = Path("corpus/posts")
QUERIES = Path("bench/queries.txt")
USAGE = "usage: python -m sift search <query> | stats | bench"


@timed
def load_index(
    root: Path, pipeline: Pipeline | None = None
) -> tuple[list[Document], InvertedIndex]:
    """Read, analyze and index every Markdown file under root.

    pipeline defaults to build_pipeline().

    The doc_id of a document is its position in the sorted path list.
    """
    pipeline = pipeline or build_pipeline()
    documents: list[Document] = []
    index = InvertedIndex()
    for doc in iter_documents(root):
        documents.append(doc)
        index.add(
            doc,
            pipeline.analyze(doc.body),
            pipeline.analyze(doc.title),
        )
    return documents, index


def run_search(words: list[str]) -> None:
    """Print the top 10 documents for the query made of words.

    The words are joined with spaces back into one query string, so
    ``search '"device tree"'`` and ``search device tree`` both work.
    """
    start = time.perf_counter()
    pipeline = build_pipeline()
    documents, index = load_index(CORPUS, pipeline)
    searcher = Searcher(index, pipeline=pipeline)
    built = time.perf_counter()
    try:
        result = searcher.search(" ".join(words))
    except QuerySyntaxError as error:
        sys.exit(error.render())
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


def main() -> None:
    """Dispatch the subcommand given on the command line."""
    args = sys.argv[1:]
    if args[:1] == ["search"] and len(args) > 1:
        run_search(args[1:])
    elif args == ["stats"]:
        run_stats()
    elif args == ["bench"]:
        run_bench()
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
