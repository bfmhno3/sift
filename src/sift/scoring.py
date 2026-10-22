"""Ranking: TF-IDF, BM25 and the top-k selection."""

import functools
import heapq
import math
from collections.abc import Mapping


@functools.cache
def idf(df: int, n_docs: int) -> float:
    """Return the smoothed inverse document frequency of a term.

    ``log(1 + n_docs / df)`` stays positive even for a term that
    appears in every document. The result depends only on the two
    integers, so it is cached.

    >>> round(idf(1, 3), 4)
    1.3863
    >>> idf(3, 3) > 0
    True
    """
    return math.log(1 + n_docs / df)


def tf_idf(tf: int, df: int, n_docs: int) -> float:
    """Return the TF-IDF weight of a term in one document.

    >>> round(tf_idf(2, 1, 3), 4)
    2.7726
    """
    return tf * idf(df, n_docs)


def bm25(
    tf: int,
    df: int,
    doc_len: int,
    avg_len: float,
    n_docs: int,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    """Return the BM25 weight of a term in one document.

    ``idf = log(1 + (n_docs - df + 0.5) / (df + 0.5))`` is never
    negative. The tf part saturates: ``tf * (k1 + 1) / (tf + k1 *
    norm)`` with ``norm = 1 - b + b * doc_len / avg_len``. b = 0 turns
    length normalization off, b = 1 applies it fully.

    >>> round(bm25(tf=1, df=1, doc_len=100, avg_len=100.0, n_docs=3), 4)
    0.9808
    >>> short = bm25(2, 1, 50, 100.0, 10)
    >>> long = bm25(2, 1, 200, 100.0, 10)
    >>> short > long
    True
    """
    idf_part = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    norm = 1 - b + b * doc_len / avg_len
    return idf_part * tf * (k1 + 1) / (tf + k1 * norm)


def top_k(scores: Mapping[int, float], k: int) -> list[tuple[int, float]]:
    """Return the k best (doc_id, score) pairs, best first.

    heapq.nlargest keeps a heap of k items instead of sorting every
    score. Equal scores are ordered by the smaller doc_id.

    >>> top_k({1: 0.5, 2: 0.9, 3: 0.9}, 2)
    [(2, 0.9), (3, 0.9)]
    >>> top_k({}, 5)
    []
    """
    return heapq.nlargest(
        k, scores.items(), key=lambda item: (item[1], -item[0])
    )
