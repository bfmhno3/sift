"""Tables and curves about the corpus: pandas frames, Zipf and Heaps.

``corpus_frame`` and ``query_log_frame`` return DataFrames; the
word-count helpers return numpy arrays, because a rank-frequency
curve is a vector and not a table.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from sift.analytics.vectors import TermIndex

CORPUS_COLUMNS = (
    "doc_id",
    "title",
    "published",
    "category",
    "series",
    "n_tags",
    "tokens",
    "chars",
)
QUERY_COLUMNS = ("at", "query", "total", "took_ms")


def corpus_frame(index: TermIndex) -> pd.DataFrame:
    """Return one row per live document, in doc_id order.

    Columns: ``doc_id``, ``title``, ``published`` (datetime64 in
    Asia/Shanghai), ``category``, ``series`` (missing values are
    ``None``), ``n_tags``, ``tokens`` (indexed tokens of the body)
    and ``chars`` (characters of the body).
    """
    docs = [index.documents[doc_id] for doc_id in sorted(index.documents)]
    return pd.DataFrame(
        {
            "doc_id": [doc.doc_id for doc in docs],
            "title": [doc.title for doc in docs],
            "published": pd.to_datetime([doc.published for doc in docs]),
            "category": [doc.category for doc in docs],
            "series": [doc.series for doc in docs],
            "n_tags": [len(doc.tags) for doc in docs],
            "tokens": [index.doc_len(doc.doc_id) for doc in docs],
            "chars": [len(doc.body) for doc in docs],
        },
        columns=list(CORPUS_COLUMNS),
    )


def query_log_frame(db: Path) -> pd.DataFrame:
    """Return the query log of the database at db, oldest first.

    Columns: ``at`` (datetime64 in UTC), ``query``, ``total`` and
    ``took_ms``. A database without a log gives an empty frame.
    """
    sql = f"SELECT {', '.join(QUERY_COLUMNS)} FROM query_log ORDER BY id"
    with sqlite3.connect(db) as conn:
        frame = pd.read_sql(sql, conn)
    frame["at"] = pd.to_datetime(frame["at"], utc=True)
    return frame


def posts_per_month(frame: pd.DataFrame) -> pd.Series[int]:
    """Count the posts of each calendar month, empty months included.

    The index holds the first day of each month, from the month of
    the first post to the month of the last one.
    """
    dated = frame.set_index("published")
    return dated["doc_id"].resample("MS").count()


def term_counts(index: TermIndex) -> NDArray[np.int64]:
    """Return the corpus frequency of every term, largest first."""
    counts = [
        sum(posting.tf for posting in index[term]) for term in sorted(index)
    ]
    return np.sort(np.asarray(counts, dtype=np.int64))[::-1]


@dataclass(frozen=True, slots=True)
class PowerLaw:
    """A fitted ``scale * x ** exponent`` curve."""

    scale: float
    exponent: float

    def __call__(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Return the curve at x."""
        return self.scale * x**self.exponent


def fit_power_law(
    x: NDArray[np.float64] | NDArray[np.int64],
    y: NDArray[np.float64] | NDArray[np.int64],
) -> PowerLaw:
    """Fit ``y = scale * x ** exponent``: a line in log-log space."""
    slope, intercept = np.polyfit(np.log(x), np.log(y), 1)
    return PowerLaw(scale=float(np.exp(intercept)), exponent=float(slope))


def zipf_fit(counts: NDArray[np.int64], max_rank: int = 1000) -> PowerLaw:
    """Fit frequency against rank over the first max_rank ranks.

    counts must be sorted largest first. The exponent is negative
    (Zipf's law says about -1). The long tail of words seen once or
    twice is a staircase, not a line, so it stays out of the fit.
    """
    ranks = np.arange(1, min(len(counts), max_rank) + 1)
    return fit_power_law(ranks, counts[: len(ranks)])


def vocabulary_growth(
    index: TermIndex,
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Return ``(tokens, vocabulary)`` after each document.

    The documents are read in doc_id order: after document i, the
    corpus holds ``tokens[i]`` tokens and ``vocabulary[i]`` distinct
    terms.
    """
    doc_ids = sorted(index.documents)
    row_of = {doc_id: row for row, doc_id in enumerate(doc_ids)}
    first_seen: list[int] = []
    for term in index:
        rows = [row_of[p.doc_id] for p in index[term] if p.doc_id in row_of]
        if rows:
            first_seen.append(min(rows))
    new_terms = np.bincount(first_seen, minlength=len(doc_ids))
    lengths = [index.doc_len(doc_id) for doc_id in doc_ids]
    return np.cumsum(lengths, dtype=np.int64), np.cumsum(new_terms)


def heaps_fit(
    tokens: NDArray[np.int64], vocabulary: NDArray[np.int64]
) -> PowerLaw:
    """Fit ``V(n) = K * n ** beta``; ``scale`` is K, ``exponent`` beta."""
    return fit_power_law(tokens, vocabulary)
