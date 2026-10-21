"""Ranking: TF-IDF with a cached idf."""

import functools
import math


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
