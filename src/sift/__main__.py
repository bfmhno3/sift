"""Search: python -m sift search <word>... | python -m sift stats."""

import sys
import time
from collections import Counter
from collections.abc import Callable
from functools import reduce
from operator import and_
from pathlib import Path

from sift.analysis import Pipeline, build_pipeline
from sift.corpus import iter_documents
from sift.document import Document
from sift.index import InvertedIndex, PostingList
from sift.scoring import tf_idf
from sift.util import timed

CORPUS = Path("corpus/posts")
USAGE = "usage: python -m sift search <word>... | python -m sift stats"


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
        index.add(doc, pipeline.analyze(doc.body))
    return documents, index


def search_index(
    index: InvertedIndex,
    words: list[str],
    n_docs: int,
    scoring: Callable[[int, int, int], float] = tf_idf,
    pipeline: Pipeline | None = None,
) -> list[tuple[float, int]]:
    """Return (score, doc_id) of documents holding every query token.

    The documents come from intersecting the posting lists with ``&``.
    A document scores the sum over query terms of
    ``scoring(tf, df, n_docs)``. Sorted by score descending, then
    doc_id. pipeline must be the one that built the index; it defaults
    to build_pipeline().
    """
    pipeline = pipeline or build_pipeline()
    terms = list(
        dict.fromkeys(token for w in words for token in pipeline.terms(w))
    )
    if not terms:
        return []
    lists = [index[t] if t in index else PostingList() for t in terms]
    matching = reduce(and_, lists)
    tfs = [{p.doc_id: p.tf for p in plist} for plist in lists]
    hits = [
        (
            sum(
                scoring(tf[doc_id], len(plist), n_docs)
                for tf, plist in zip(tfs, lists, strict=True)
            ),
            doc_id,
        )
        for doc_id in matching.doc_ids()
    ]
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    return hits


def run_search(words: list[str]) -> None:
    """Print the top 10 files by TF-IDF holding every word."""
    start = time.perf_counter()
    pipeline = build_pipeline()
    documents, index = load_index(CORPUS, pipeline)
    built = time.perf_counter()
    hits = search_index(index, words, len(documents), pipeline=pipeline)
    end = time.perf_counter()
    for score, doc_id in hits[:10]:
        print(f"{score:8.3f}  {documents[doc_id].path}")
    print(
        f"{len(hits)} hits in {len(documents)} files: "
        f"index built in {(built - start) * 1000:.1f} ms, "
        f"query took {(end - built) * 1000:.3f} ms"
    )


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
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
