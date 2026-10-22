"""Top 3 by plain tf and by TF-IDF; idf cache hit rate on the corpus."""

from collections.abc import Callable
from functools import reduce
from operator import and_

from sift.__main__ import CORPUS, load_index
from sift.analysis import build_pipeline
from sift.index import InvertedIndex, PostingList
from sift.scoring import idf, tf_idf

QUERIES = ["linux device", "矩阵 matrix", "python function"]


def plain_tf(tf: int, df: int, n_docs: int) -> float:
    """Score a term by its raw frequency, ignoring df."""
    return tf


def search_index(
    index: InvertedIndex,
    words: list[str],
    n_docs: int,
    scoring: Callable[[int, int, int], float] = tf_idf,
) -> list[tuple[float, int]]:
    """Return (score, doc_id) of documents holding every word.

    This is the chapter 4 search, kept here so the lab can swap the
    scoring function: AND by ``&``, score = sum of scoring(tf, df, n).
    """
    pipeline = build_pipeline()
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


def main() -> None:
    """Compare the two rankings, then report idf cache statistics."""
    documents, index = load_index(CORPUS)
    n_docs = len(documents)
    idf.cache_clear()
    for query in QUERIES:
        words = query.split()
        by_tf = search_index(index, words, n_docs, plain_tf)
        by_idf = search_index(index, words, n_docs)
        print(f"query: {query!r}: {len(by_idf)} hits")
        print("  plain tf")
        for score, doc_id in by_tf[:3]:
            print(f"    {score:8.0f}  {documents[doc_id].path.name}")
        print("  tf-idf")
        for score, doc_id in by_idf[:3]:
            print(f"    {score:8.3f}  {documents[doc_id].path.name}")
    info = idf.cache_info()
    calls = info.hits + info.misses
    print(info)
    print(f"idf calls {calls}, hit rate {info.hits / calls:.4%}")


if __name__ == "__main__":
    main()
