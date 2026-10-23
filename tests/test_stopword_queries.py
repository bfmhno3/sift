"""Queries with stopwords: ignored words and phrase gaps."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sift.analysis import build_pipeline
from sift.document import Document
from sift.index import IndexWriter, InvertedIndex
from sift.query import parse
from sift.query.evaluate import evaluate
from sift.search import Searcher

PIPELINE = build_pipeline(["mixed", "nfkc", "stopwords"])
TEXTS = [
    "memory safety in the kernel",  # 0
    "the top of the stack grows down",  # 1
    "top stack frames",  # 2
    "the top of a heap and a stack",  # 3
    "kernel memory",  # 4
]


@pytest.fixture(scope="module")
def index() -> InvertedIndex:
    index = InvertedIndex()
    with IndexWriter(index, PIPELINE) as writer:
        for doc_id, text in enumerate(TEXTS):
            writer.add(
                Document(
                    doc_id,
                    Path(f"{doc_id}.md"),
                    f"Title {doc_id}",
                    datetime(2026, 1, 1, tzinfo=UTC),
                    None,
                    (),
                    None,
                    None,
                    text,
                )
            )
    return index


def ids(query: str, index: InvertedIndex) -> list[int]:
    return evaluate(parse(query), index, PIPELINE).doc_ids()


def test_stopwords_keep_their_positions(index: InvertedIndex) -> None:
    assert [p.positions for p in index["top"]] == [(1,), (0,), (1,)]
    assert index["stack"][0].positions == (4,)


def test_and_ignores_a_stopword(index: InvertedIndex) -> None:
    assert ids("memory of the kernel", index) == [0, 4]
    assert ids("memory AND the", index) == ids("memory", index)


def test_or_and_not_ignore_a_stopword(index: InvertedIndex) -> None:
    assert ids("kernel OR the", index) == ids("kernel", index)
    assert ids("the OR kernel", index) == ids("kernel", index)
    assert ids("kernel AND NOT the", index) == ids("kernel", index)
    assert ids("kernel -the", index) == ids("kernel", index)


def test_query_of_only_stopwords_matches_nothing(index: InvertedIndex) -> None:
    for query in ("the", "of the", "the OR of", "the AND of", "the*"):
        assert ids(query, index) == [], query


def test_phrase_honours_the_gap(index: InvertedIndex) -> None:
    assert ids('"top of the stack"', index) == [1]
    assert ids('"top of a heap"', index) == [3]
    assert ids('"top stack"', index) == [2]


def test_phrase_gap_must_have_the_right_width(index: InvertedIndex) -> None:
    assert ids('"top the stack"', index) == []
    assert ids('"top of the of the stack"', index) == []


def test_title_phrase_gap() -> None:
    index = InvertedIndex()
    with IndexWriter(index, PIPELINE) as writer:
        for doc_id, title in enumerate(["Top of the stack", "Top stack"]):
            writer.add(
                Document(
                    doc_id,
                    Path(f"{doc_id}.md"),
                    title,
                    datetime(2026, 1, 1, tzinfo=UTC),
                    None,
                    (),
                    None,
                    None,
                    "body",
                )
            )
    assert ids('title:"top of the stack"', index) == [0]
    assert ids("title:the", index) == []


def test_searcher_scores_with_an_ignored_word(index: InvertedIndex) -> None:
    searcher = Searcher(index, pipeline=PIPELINE)
    result = searcher.search("memory of the kernel")
    assert sorted(h.doc_id for h in result.hits) == [0, 4]
    assert searcher.search("the").total == 0
    assert searcher.search('"top of the stack"').hits[0].doc_id == 1
