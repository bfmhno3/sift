"""Tests for sift.search."""

import pytest

from sift.errors import QuerySyntaxError
from sift.index import InvertedIndex
from sift.query import And, Field, Not, Or, Phrase, Prefix, Term
from sift.search import Searcher, positive_leaves


def test_positive_leaves_skip_not_and_fields() -> None:
    tree = And(
        Or(Term("a"), Prefix("b")),
        And(Not(Term("c")), And(Phrase(("d", "e")), Field("tag", Term("f")))),
    )
    assert positive_leaves(tree) == [
        Term("a"),
        Prefix("b"),
        Phrase(("d", "e")),
    ]


@pytest.fixture
def searcher(mini_index: InvertedIndex) -> Searcher:
    """Return a Searcher over the shared mini index."""
    return Searcher(mini_index)


def test_result_fields(searcher: Searcher) -> None:
    result = searcher.search("chain")
    assert result.query == "chain"
    assert result.total == 1
    assert result.took_ms >= 0
    (hit,) = result.hits
    assert hit.doc_id == 1
    assert hit.title == "Fixing a bicycle chain"
    assert hit.path.name == "bicycle-repair.md"
    assert hit.score > 0
    assert any(is_hit for _, is_hit in hit.snippet)


def test_no_match(searcher: Searcher) -> None:
    result = searcher.search("zebra")
    assert (result.total, result.hits) == (0, [])


def test_hits_are_ranked_by_score_descending(searcher: Searcher) -> None:
    result = searcher.search("tea OR river OR chain")
    scores = [hit.score for hit in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert result.total == len(result.hits) == 4


def test_limit_caps_hits_but_not_total(searcher: Searcher) -> None:
    result = searcher.search("category:notes OR tea", limit=3)
    assert result.total == 8
    assert len(result.hits) == 3


def test_more_occurrences_rank_higher(searcher: Searcher) -> None:
    result = searcher.search("tea")
    assert [h.doc_id for h in result.hits] == [7, 6]


def test_field_filters_select_without_scoring(searcher: Searcher) -> None:
    result = searcher.search("tag:life")
    assert [h.doc_id for h in result.hits] == [7]
    assert result.hits[0].score == 0.0


def test_not_removes_documents(searcher: Searcher) -> None:
    ids = {h.doc_id for h in searcher.search("river -tag:桥").hits}
    assert ids == set()
    ids = {h.doc_id for h in searcher.search("tea -green").hits}
    assert ids == set()


def test_phrase_snippet_highlights_each_word(searcher: Searcher) -> None:
    (hit,) = searcher.search('"chain tool"').hits
    marked = {text.lower() for text, is_hit in hit.snippet if is_hit}
    assert marked == {"chain", "tool"}


def test_prefix_snippet_highlights_the_expansion(searcher: Searcher) -> None:
    (hit,) = searcher.search("chai*").hits
    marked = {text.lower() for text, is_hit in hit.snippet if is_hit}
    assert marked == {"chain"}


def test_k1_and_b_change_the_score(mini_index: InvertedIndex) -> None:
    base = Searcher(mini_index).search("chain").hits[0].score
    flat = Searcher(mini_index, k1=0.1, b=0).search("chain").hits[0].score
    assert base != flat


def test_syntax_error_propagates(searcher: Searcher) -> None:
    with pytest.raises(QuerySyntaxError, match="unterminated phrase"):
        searcher.search('"oops')


def test_chinese_query(searcher: Searcher) -> None:
    result = searcher.search("编译器")
    assert [h.doc_id for h in result.hits] == [3]


def test_query_terms_are_cached_per_word(mini_index: InvertedIndex) -> None:
    searcher = Searcher(mini_index)
    first = searcher.search("chain tool")
    assert searcher.term_cache.misses == 2
    again = searcher.search("chain tool")
    assert searcher.term_cache.hits == 2
    assert [h.snippet for h in again.hits] == [h.snippet for h in first.hits]


def test_a_tiny_cache_still_gives_the_same_snippets(
    mini_index: InvertedIndex,
) -> None:
    plain = Searcher(mini_index, cache_size=1).search("chain tool")
    cached = Searcher(mini_index).search("chain tool")
    assert [h.snippet for h in plain.hits] == [h.snippet for h in cached.hits]
