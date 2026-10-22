"""Tests for sift.scoring."""

import math
from itertools import pairwise

import pytest

from sift.scoring import bm25, idf, tf_idf, top_k


def test_idf_formula_and_cache() -> None:
    idf.cache_clear()
    first = idf(1, 3)
    assert idf(1, 3) is first
    assert first == pytest.approx(math.log(4))
    info = idf.cache_info()
    assert (info.hits, info.misses) == (1, 1)


def test_idf_stays_positive_for_a_term_in_every_document() -> None:
    assert idf(10, 10) == pytest.approx(math.log(2))


def test_rarer_terms_weigh_more() -> None:
    assert idf(1, 100) > idf(10, 100) > idf(100, 100)


def test_tf_idf_is_linear_in_tf() -> None:
    assert tf_idf(3, 2, 10) == pytest.approx(3 * tf_idf(1, 2, 10))
    assert tf_idf(0, 2, 10) == 0


def test_bm25_matches_the_formula_by_hand() -> None:
    tf, df, doc_len, avg_len, n_docs = 3, 2, 120, 100.0, 50
    k1, b = 1.2, 0.75
    idf_part = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    norm = 1 - b + b * doc_len / avg_len
    expected = idf_part * tf * (k1 + 1) / (tf + k1 * norm)
    assert bm25(tf, df, doc_len, avg_len, n_docs) == pytest.approx(expected)


def test_bm25_saturates_in_tf() -> None:
    gains = [
        bm25(tf + 1, 1, 100, 100.0, 10) - bm25(tf, 1, 100, 100.0, 10)
        for tf in range(1, 6)
    ]
    assert all(g1 > g2 > 0 for g1, g2 in pairwise(gains))
    limit = math.log(1 + 9.5 / 1.5) * (1.2 + 1)
    assert bm25(10_000, 1, 100, 100.0, 10) < limit


def test_bm25_b_controls_length_normalization() -> None:
    longer = bm25(2, 1, 400, 100.0, 10, b=0)
    assert longer == bm25(2, 1, 25, 100.0, 10, b=0)
    assert bm25(2, 1, 400, 100.0, 10, b=1) < bm25(2, 1, 25, 100.0, 10, b=1)


def test_bm25_never_negative_even_when_df_is_n_docs() -> None:
    assert bm25(1, 10, 100, 100.0, 10) > 0


def test_top_k_orders_by_score_then_smaller_doc_id() -> None:
    scores = {5: 1.0, 2: 3.0, 9: 3.0, 1: 0.5}
    assert top_k(scores, 3) == [(2, 3.0), (9, 3.0), (5, 1.0)]


@pytest.mark.parametrize(("k", "count"), [(0, 0), (1, 1), (4, 4), (99, 4)])
def test_top_k_sizes(k: int, count: int) -> None:
    assert len(top_k({1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}, k)) == count


def test_top_k_of_nothing() -> None:
    assert top_k({}, 3) == []
