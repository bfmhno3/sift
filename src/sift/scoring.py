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
    """
    return math.log(1 + n_docs / df)


def tf_idf(tf: int, df: int, n_docs: int) -> float:
    """Return the TF-IDF weight of a term in one document."""
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
    """
    idf_part = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    norm = 1 - b + b * doc_len / avg_len
    return idf_part * tf * (k1 + 1) / (tf + k1 * norm)


def top_k(scores: Mapping[int, float], k: int) -> list[tuple[int, float]]:
    """Return the k best (doc_id, score) pairs, best first.

    heapq.nlargest keeps a heap of k items instead of sorting every
    score. Equal scores are ordered by the smaller doc_id.
    """
    return heapq.nlargest(
        k, scores.items(), key=lambda item: (item[1], -item[0])
    )
