"""TF-IDF vectors of the documents and the cosine similarity of posts.

The matrix has one row per live document (in doc_id order) and one
column per term (in sorted order). A cell is
``(1 + ln tf) * (ln((1 + N) / (1 + df)) + 1)``, and every row is
scaled to length 1, so the dot product of two rows is their cosine.
float32 halves the memory of float64 and keeps the ranking.

Only the commands that need numpy import this module.
"""

from collections.abc import Iterator
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from sift.errors import SiftError
from sift.index import IndexView, PostingList


class TermIndex(IndexView, Protocol):
    """An IndexView that also lists its terms and their postings.

    InvertedIndex and SegmentIndex both conform.
    """

    def __iter__(self) -> Iterator[str]:
        """Iterate over the terms."""
        ...

    def __getitem__(self, term: str, /) -> PostingList:
        """Return the postings of term."""
        ...


def tfidf_matrix(index: TermIndex) -> tuple[NDArray[np.float32], list[str]]:
    """Return ``(matrix, vocab)`` for the live documents of index.

    Row i belongs to ``sorted(index.documents)[i]`` and column j to
    ``vocab[j]``. Rows are L2-normalized; the row of a document
    without terms stays all zero.
    """
    doc_ids = sorted(index.documents)
    row_of = {doc_id: row for row, doc_id in enumerate(doc_ids)}
    vocab: list[str] = []
    rows: list[int] = []
    cols: list[int] = []
    freqs: list[int] = []
    for term in sorted(index):
        before = len(rows)
        for posting in index[term]:
            row = row_of.get(posting.doc_id)
            if row is not None:
                rows.append(row)
                cols.append(len(vocab))
                freqs.append(posting.tf)
        if len(rows) > before:
            vocab.append(term)
    col = np.asarray(cols, dtype=np.intp)
    tf = np.asarray(freqs, dtype=np.float32)
    df = np.bincount(col, minlength=len(vocab)).astype(np.float32)
    idf = np.log((1 + len(doc_ids)) / (1 + df), dtype=np.float32) + 1
    matrix = np.zeros((len(doc_ids), len(vocab)), dtype=np.float32)
    matrix[np.asarray(rows, dtype=np.intp), col] = (1 + np.log(tf)) * idf[col]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, norms, out=matrix, where=norms > 0)
    return matrix, vocab


def similar(
    index: TermIndex, doc_id: int, k: int = 5
) -> list[tuple[int, float]]:
    """Return the k documents closest to doc_id as ``(doc_id, score)``.

    The score is the cosine of the TF-IDF vectors, from 1.0 down to 0.0.
    The document itself comes first (score 1.0); ties keep doc_id
    order. Raise ValueError if k < 1 and SiftError if doc_id is not
    a live document.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, not {k}")
    doc_ids = sorted(index.documents)
    try:
        row = doc_ids.index(doc_id)
    except ValueError:
        raise SiftError(f"no document with id {doc_id}") from None
    matrix, _ = tfidf_matrix(index)
    scores = np.clip(matrix @ matrix[row], 0.0, 1.0)
    best = np.argsort(-scores, kind="stable")[:k]
    return [(doc_ids[i], float(scores[i])) for i in best]


def top_pairs(index: TermIndex, n: int = 5) -> list[tuple[int, int, float]]:
    """Return the n most similar pairs ``(doc_a, doc_b, score)``.

    Each pair appears once, with doc_a < doc_b, best first.
    """
    doc_ids = sorted(index.documents)
    matrix, _ = tfidf_matrix(index)
    cosines = np.clip(matrix @ matrix.T, 0.0, 1.0)
    first, second = np.triu_indices(len(doc_ids), k=1)
    best = np.argsort(-cosines[first, second], kind="stable")[:n]
    return [
        (
            doc_ids[first[i]],
            doc_ids[second[i]],
            float(cosines[first[i], second[i]]),
        )
        for i in best
    ]
