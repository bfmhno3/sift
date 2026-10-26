"""The analytics package: vectors, frames, fits and figures."""

import sqlite3
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

from sift.analytics import plots, stats
from sift.analytics.report import write_report
from sift.analytics.vectors import similar, tfidf_matrix, top_pairs
from sift.errors import SiftError
from sift.index import InvertedIndex
from sift.storage.db import log_query, open_db


def test_matrix_is_float32_with_unit_rows(mini_index: InvertedIndex) -> None:
    matrix, vocab = tfidf_matrix(mini_index)
    assert matrix.dtype == np.float32
    assert matrix.shape == (mini_index.n_docs, len(vocab))
    assert vocab == sorted(vocab)
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-6)
    assert (matrix >= 0).all()


def test_a_document_is_most_similar_to_itself(
    mini_index: InvertedIndex,
) -> None:
    for doc_id in mini_index.documents:
        found = similar(mini_index, doc_id, k=3)
        assert found[0][0] == doc_id
        assert found[0][1] == pytest.approx(1.0, abs=1e-6)


def test_similar_scores_are_in_0_1_and_sorted(
    mini_index: InvertedIndex,
) -> None:
    found = similar(mini_index, 0, k=mini_index.n_docs)
    scores = [score for _, score in found]
    assert len(found) == mini_index.n_docs
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores == sorted(scores, reverse=True)
    assert len({doc_id for doc_id, _ in found}) == len(found)


def test_similar_k_larger_than_the_corpus_returns_all(
    mini_index: InvertedIndex,
) -> None:
    assert len(similar(mini_index, 0, k=100)) == mini_index.n_docs


def test_similar_rejects_unknown_doc_and_bad_k(
    mini_index: InvertedIndex,
) -> None:
    with pytest.raises(SiftError, match="no document with id 99"):
        similar(mini_index, 99)
    with pytest.raises(ValueError, match="at least 1"):
        similar(mini_index, 0, k=0)


def test_similar_skips_removed_documents(mini_docs: list) -> None:
    from sift.index import IndexWriter

    index = InvertedIndex()
    with IndexWriter(index) as writer:
        for doc in mini_docs:
            writer.add(doc)
    index.remove([2])
    ids = [doc_id for doc_id, _ in similar(index, 0, k=10)]
    assert 2 not in ids
    assert len(ids) == len(mini_docs) - 1


def test_top_pairs_are_ordered_and_unique(mini_index: InvertedIndex) -> None:
    pairs = top_pairs(mini_index, 4)
    assert len(pairs) == 4
    assert all(first < second for first, second, _ in pairs)
    scores = [score for _, _, score in pairs]
    assert scores == sorted(scores, reverse=True)
    assert len({(first, second) for first, second, _ in pairs}) == 4
    first, second, score = pairs[0]
    again = dict(similar(mini_index, first, k=mini_index.n_docs))
    assert again[second] == pytest.approx(score, abs=1e-6)


def test_corpus_frame_columns_and_rows(mini_index: InvertedIndex) -> None:
    frame = stats.corpus_frame(mini_index)
    assert tuple(frame.columns) == stats.CORPUS_COLUMNS
    assert frame["doc_id"].tolist() == sorted(mini_index.documents)
    assert len(frame) == mini_index.n_docs
    assert str(frame["published"].dtype).startswith("datetime64")
    assert frame["tokens"].tolist() == [
        mini_index.doc_len(doc_id) for doc_id in frame["doc_id"]
    ]
    assert (frame["chars"] > 0).all()


def test_posts_per_month_counts_every_post(mini_index: InvertedIndex) -> None:
    frame = stats.corpus_frame(mini_index)
    monthly = stats.posts_per_month(frame)
    assert int(monthly.sum()) == len(frame)
    assert all(stamp.day == 1 for stamp in monthly.index)


def test_query_log_frame_reads_the_log(tmp_path: Path) -> None:
    db = tmp_path / "sift.db"
    log_query(db, "chain", 3, 1.5)
    log_query(db, "编译", 0, 0.25)
    frame = stats.query_log_frame(db)
    assert tuple(frame.columns) == stats.QUERY_COLUMNS
    assert frame["query"].tolist() == ["chain", "编译"]
    assert frame["took_ms"].tolist() == [1.5, 0.25]
    assert str(frame["at"].dtype) == "datetime64[us, UTC]"


def test_query_log_frame_of_an_empty_log(tmp_path: Path) -> None:
    db = tmp_path / "sift.db"
    open_db(db).kw["bind"].dispose()
    frame = stats.query_log_frame(db)
    assert len(frame) == 0
    assert tuple(frame.columns) == stats.QUERY_COLUMNS


def test_query_log_frame_without_a_log_table_fails(tmp_path: Path) -> None:
    db = tmp_path / "other.db"
    sqlite3.connect(db).close()
    with pytest.raises(pd.errors.DatabaseError):
        stats.query_log_frame(db)


def test_zipf_fit_recovers_a_perfect_law() -> None:
    counts = np.round(100_000 / np.arange(1, 2001)).astype(np.int64)
    fit = stats.zipf_fit(counts)
    assert fit.exponent == pytest.approx(-1.0, abs=0.01)
    assert fit.scale == pytest.approx(100_000, rel=0.02)


def test_zipf_fit_with_fewer_terms_than_max_rank() -> None:
    counts = np.array([100, 50, 33, 25], dtype=np.int64)
    assert stats.zipf_fit(counts).exponent == pytest.approx(-1.0, abs=0.05)


def test_term_counts_sum_to_the_token_count(mini_index: InvertedIndex) -> None:
    counts = stats.term_counts(mini_index)
    assert counts.tolist() == sorted(counts.tolist(), reverse=True)
    total = sum(mini_index.doc_len(doc_id) for doc_id in mini_index.documents)
    assert int(counts.sum()) == total


def test_vocabulary_growth_is_cumulative(mini_index: InvertedIndex) -> None:
    tokens, vocabulary = stats.vocabulary_growth(mini_index)
    assert len(tokens) == len(vocabulary) == mini_index.n_docs
    assert (np.diff(tokens) > 0).all()
    assert (np.diff(vocabulary) >= 0).all()
    assert int(vocabulary[-1]) == len(mini_index)
    fit = stats.heaps_fit(tokens, vocabulary)
    assert 0.0 < fit.exponent < 1.0


def test_power_law_fit_recovers_k_and_beta() -> None:
    n = np.arange(100, 5000, 100)
    v = (7.5 * n**0.6).astype(np.float64)
    fit = stats.fit_power_law(n, v)
    assert fit.scale == pytest.approx(7.5, rel=1e-6)
    assert fit.exponent == pytest.approx(0.6, rel=1e-6)
    assert fit(np.array([100.0]))[0] == pytest.approx(7.5 * 100**0.6)


def test_configure_matplotlib_registers_the_cjk_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with matplotlib.rc_context():
        monkeypatch.delenv(plots.FONT_ENV, raising=False)
        assert plots.configure_matplotlib() is None
        assert matplotlib.get_backend().lower() == "agg"


def test_configure_matplotlib_sets_the_font_family() -> None:
    import os

    if not os.environ.get(plots.FONT_ENV):
        pytest.skip("SIFT_CJK_FONT is not set")
    with matplotlib.rc_context():
        family = plots.configure_matplotlib()
        assert family
        assert matplotlib.rcParams["font.family"] == [family]


def test_write_report_makes_figures_and_a_table(
    mini_index: InvertedIndex, tmp_path: Path
) -> None:
    db = tmp_path / "sift.db"
    log_query(db, "chain", 3, 1.5)
    out = tmp_path / "nested" / "report"
    with matplotlib.rc_context():
        written = write_report(mini_index, db, out)
    assert [path.name for path in written] == [
        "zipf.png",
        "heaps.png",
        "posts-per-month.png",
        "latency-hist.png",
        "report.md",
    ]
    for path in written[:4]:
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "| documents | 8 |" in text
    assert "| logged queries | 1 |" in text
    assert text.count("| 0.") >= 5
