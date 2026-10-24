"""Tests for sift.index: postings, posting lists, the index, writer."""

import pytest

from sift.document import Document
from sift.index import IndexWriter, InvertedIndex, Posting, PostingList


def plist(**docs: tuple[int, ...]) -> PostingList:
    """Build a PostingList from d<doc_id>=positions keywords."""
    return PostingList(Posting(int(k[1:]), v) for k, v in docs.items())


def snapshot(index: InvertedIndex) -> dict[str, list[Posting]]:
    """Copy the postings: append changes a PostingList in place."""
    return {term: list(index[term]) for term in index}


def test_posting_tf_counts_positions() -> None:
    assert Posting(3, (1, 4, 9)).tf == 3
    assert Posting(3, ()).tf == 0


def test_posting_is_frozen() -> None:
    with pytest.raises(AttributeError):
        Posting(1, ()).doc_id = 2  # type: ignore[misc]


def test_postinglist_sorts_and_refuses_duplicates() -> None:
    assert plist(d5=(0,), d2=(1,)).doc_ids() == [2, 5]
    with pytest.raises(ValueError, match="duplicate doc_id"):
        PostingList([Posting(1, ()), Posting(1, (2,))])


def test_append_needs_increasing_ids() -> None:
    pl = plist(d1=(0,))
    pl.append(Posting(2, ()))
    with pytest.raises(ValueError, match="doc_id 2 is not increasing"):
        pl.append(Posting(2, ()))
    assert len(pl) == 2


def test_sequence_protocol() -> None:
    pl = plist(d1=(0,), d4=(2, 3), d9=())
    assert len(pl) == 3
    assert pl[1] == Posting(4, (2, 3))
    assert 4 in pl and 5 not in pl
    assert [p.doc_id for p in pl] == [1, 4, 9]
    assert repr(pl) == (
        "PostingList([Posting(doc_id=1, positions=(0,)), "
        "Posting(doc_id=4, positions=(2, 3)), "
        "Posting(doc_id=9, positions=())])"
    )


def test_equality_compares_postings() -> None:
    assert plist(d1=(0,)) == plist(d1=(0,))
    assert plist(d1=(0,)) != plist(d1=(1,))
    assert plist(d1=(0,)) != [Posting(1, (0,))]


def test_set_algebra_on_a_small_example() -> None:
    a = plist(d1=(0,), d2=(1,), d3=(2,))
    b = plist(d2=(5,), d3=(2, 7), d4=(0,))
    assert (a & b).doc_ids() == [2, 3]
    assert (a | b).doc_ids() == [1, 2, 3, 4]
    assert (a - b).doc_ids() == [1]
    assert (b - a).doc_ids() == [4]


def test_both_sides_merge_their_positions() -> None:
    a = plist(d1=(0, 4))
    b = plist(d1=(2, 4))
    assert (a & b)[0].positions == (0, 2, 4)
    assert (a | b)[0].positions == (0, 2, 4)


def test_operators_return_new_lists() -> None:
    a = plist(d1=(0,))
    assert (a | plist()) is not a
    assert a.doc_ids() == [1]


def test_operators_refuse_other_types() -> None:
    with pytest.raises(TypeError):
        plist(d1=()) & {1}
    with pytest.raises(TypeError):
        plist(d1=()) | [1]
    with pytest.raises(TypeError):
        plist(d1=()) - 1


def test_contains_is_false_for_a_non_int() -> None:
    pl = plist(d1=(), d2=())
    assert 1 in pl
    assert 3 not in pl
    assert "1" not in pl
    assert None not in pl


def test_without_drops_the_given_ids() -> None:
    pl = plist(d1=(), d2=(), d3=())
    assert pl.without([2, 99]).doc_ids() == [1, 3]


def test_index_statistics(mini_index: InvertedIndex) -> None:
    assert mini_index.n_docs == 8
    assert mini_index.avg_doc_len == pytest.approx(
        sum(mini_index.doc_len(i) for i in range(8)) / 8
    )
    assert len(mini_index) > 100


def test_index_is_a_mapping(mini_index: InvertedIndex) -> None:
    assert "chain" in mini_index
    assert "zebra" not in mini_index
    assert mini_index.get("zebra") is None
    with pytest.raises(KeyError):
        mini_index["zebra"]
    assert sorted(mini_index.keys()) == sorted(mini_index)


def test_postings_of_a_term(mini_index: InvertedIndex) -> None:
    chain = mini_index["chain"]
    assert chain.doc_ids() == [1]
    assert chain[0].tf == 8


def test_title_index_is_separate(mini_index: InvertedIndex) -> None:
    titles = mini_index.title_index
    assert titles["bicycle"].doc_ids() == [1]
    assert titles["chain"][0].positions == (3,)
    assert "tool" in mini_index
    assert "tool" not in titles


def test_terms_with_prefix(mini_index: InvertedIndex) -> None:
    terms = mini_index.terms_with_prefix("bicy")
    assert terms == ["bicycle"]
    assert mini_index.terms_with_prefix("zzz") == []
    assert mini_index.terms_with_prefix("") == sorted(mini_index)


def test_add_refreshes_the_prefix_cache(mini_docs: list[Document]) -> None:
    index = InvertedIndex()
    assert index.terms_with_prefix("a") == []
    with IndexWriter(index) as writer:
        writer.add(mini_docs[1])
    assert "a" in index.terms_with_prefix("a")


def test_empty_index_statistics() -> None:
    index = InvertedIndex()
    assert index.n_docs == 0
    assert index.avg_doc_len == 0.0
    assert list(index) == []


def test_writer_keeps_documents_on_success(
    mini_docs: list[Document],
) -> None:
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        writer.add(mini_docs[0])
        writer.add(mini_docs[1])
    assert sorted(index.documents) == [0, 1]


def test_writer_rolls_back_on_an_exception(
    mini_docs: list[Document],
) -> None:
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        writer.add(mini_docs[0])
    before = snapshot(index)
    with pytest.raises(RuntimeError, match="boom"), IndexWriter(index) as w:
        w.add(mini_docs[1])
        w.add(mini_docs[2])
        raise RuntimeError("boom")
    assert sorted(index.documents) == [0]
    assert snapshot(index) == before
    assert index.n_docs == 1
    assert all(2 not in pl for pl in index.title_index.values())


def test_writer_refuses_a_known_doc_id_and_keeps_it(
    mini_docs: list[Document],
) -> None:
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        writer.add(mini_docs[0])
    with (
        pytest.raises(ValueError, match="already indexed"),
        IndexWriter(index) as writer,
    ):
        writer.add(mini_docs[1])
        writer.add(mini_docs[0])
    assert sorted(index.documents) == [0]


def test_remove_drops_terms_that_lose_every_posting(
    mini_docs: list[Document],
) -> None:
    index = InvertedIndex()
    with IndexWriter(index) as writer:
        for doc in mini_docs:
            writer.add(doc)
    assert "chain" in index
    index.remove([1, 1000])
    assert "chain" not in index
    assert 1 not in index.documents
    assert index.n_docs == 7
