"""Property-based tests: hypothesis generates the inputs."""

import re

from hypothesis import given
from hypothesis import strategies as st

from sift.analysis import tokenize
from sift.analysis.tokenize import fold, iter_hit_spans, iter_tokens
from sift.index import Posting, PostingList
from sift.query import (
    And,
    Field,
    Kind,
    Node,
    Not,
    Or,
    Phrase,
    Prefix,
    Term,
    evaluate,
    parse,
    print_query,
)
from sift.query.lexer import FIELDS
from sift.query.lexer import iter_tokens as iter_query_tokens
from sift.query.parser import has_positive
from sift.snippet import make_snippet

# Any text at all, with a bias toward the interesting scripts: ASCII,
# CJK, fullwidth forms and ligatures that NFKC rewrites.
TEXT = st.text(
    alphabet=st.one_of(
        st.characters(),
        st.sampled_from("abcXYZ019_+# \t\n搜索引擎全文ﬁＡ㎏…"),
    ),
    max_size=60,
)


@given(TEXT)
def test_tokens_are_never_empty(text: str) -> None:
    assert all(token.text for token in iter_tokens(text))


@given(TEXT)
def test_offsets_slice_back_to_the_folded_text(text: str) -> None:
    folded = fold(text)
    for token in iter_tokens(text):
        assert 0 <= token.start < token.end <= len(folded)
        assert folded[token.start : token.end] == token.text


@given(TEXT)
def test_positions_count_tokens_from_zero(text: str) -> None:
    tokens = list(iter_tokens(text))
    assert [t.position for t in tokens] == list(range(len(tokens)))


@given(TEXT, st.sets(st.sampled_from(["a", "ab", "搜索", "索引", "全", "x_"])))
def test_hit_spans_are_the_spans_of_the_tokens_in_terms(
    text: str, terms: set[str]
) -> None:
    expected = [
        (token.start, token.end)
        for token in iter_tokens(text)
        if token.text in terms
    ]
    assert list(iter_hit_spans(text, terms)) == expected


@given(TEXT)
def test_token_starts_never_decrease(text: str) -> None:
    starts = [t.start for t in iter_tokens(text)]
    assert starts == sorted(starts)


# A word the query lexer reads back as exactly one WORD token.
WORD = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc", "Zs", "Zl", "Zp"),
        blacklist_characters='()"*',
    ),
    min_size=1,
    max_size=6,
).filter(
    lambda w: [t.kind for t in iter_query_tokens(w)] == [Kind.WORD, Kind.EOF]
)
LEAF = st.one_of(
    WORD.map(Term),
    WORD.map(Prefix),
    st.lists(WORD, max_size=3).map(lambda ws: Phrase(tuple(ws))),
    st.builds(
        Field,
        st.sampled_from(sorted(FIELDS)),
        st.one_of(
            WORD.map(Term),
            st.lists(WORD, max_size=3).map(lambda ws: Phrase(tuple(ws))),
        ),
    ),
)
NODES = st.recursive(
    LEAF,
    lambda inner: st.one_of(
        st.builds(And, inner, inner),
        st.builds(Or, inner, inner),
        st.builds(Not, inner),
    ),
    max_leaves=8,
)
QUERIES = NODES.filter(has_positive)


@given(QUERIES)
def test_parse_inverts_print_query(node: Node) -> None:
    assert parse(print_query(node)) == node


POSTING_LISTS = st.dictionaries(
    st.integers(min_value=0, max_value=40),
    st.lists(st.integers(0, 30), unique=True, max_size=5).map(
        lambda ps: tuple(sorted(ps))
    ),
    max_size=15,
).map(lambda d: PostingList(Posting(i, ps) for i, ps in d.items()))


@given(POSTING_LISTS, POSTING_LISTS)
def test_and_agrees_with_set_intersection(a, b) -> None:
    assert (a & b).doc_ids() == sorted(set(a.doc_ids()) & set(b.doc_ids()))


@given(POSTING_LISTS, POSTING_LISTS)
def test_or_agrees_with_set_union(a, b) -> None:
    assert (a | b).doc_ids() == sorted(set(a.doc_ids()) | set(b.doc_ids()))


@given(POSTING_LISTS, POSTING_LISTS)
def test_sub_agrees_with_set_difference(a, b) -> None:
    assert (a - b).doc_ids() == sorted(set(a.doc_ids()) - set(b.doc_ids()))


@given(POSTING_LISTS, POSTING_LISTS)
def test_merged_positions_are_the_sorted_union(a, b) -> None:
    by_a = {p.doc_id: set(p.positions) for p in a}
    by_b = {p.doc_id: set(p.positions) for p in b}
    for merged in (a & b, a | b):
        for posting in merged:
            want = by_a.get(posting.doc_id, set()) | by_b.get(
                posting.doc_id, set()
            )
            assert posting.positions == tuple(sorted(want))


@given(POSTING_LISTS, POSTING_LISTS)
def test_set_laws(a, b) -> None:
    assert (a & b).doc_ids() == (b & a).doc_ids()
    assert (a | b).doc_ids() == (b | a).doc_ids()
    assert ((a - b) | (a & b)).doc_ids() == a.doc_ids()
    assert not set((a - b).doc_ids()) & set(b.doc_ids())


@given(TEXT, st.integers(min_value=1, max_value=80), st.data())
def test_snippet_shows_a_slice_of_the_text(text, width, data) -> None:
    # Any text and any window: parts are non-empty, hits hold a word
    # character and the parts are cut from the text (or its folding).
    words = tokenize(text)
    chosen = (
        data.draw(st.lists(st.sampled_from(words), max_size=4))
        if (words)
        else []
    )
    parts = make_snippet(text, set(chosen), width)
    assert all(shown for shown, _ in parts)
    assert all(tokenize(shown) for shown, hit in parts if hit)
    body = "".join(shown for shown, _ in parts).strip("…")
    squeezed = (re.sub(r"\s+", " ", t) for t in (text, fold(text)))
    assert any(body.strip() in t for t in squeezed)


# The vocabulary of the mini index; "zebra" matches nothing.
WORDS = st.sampled_from(
    ["chain", "tea", "river", "bicycle", "parsing", "编译", "zebra"]
)
EXPRESSIONS = st.recursive(
    WORDS.map(Term),
    lambda inner: st.one_of(
        st.builds(And, inner, inner),
        st.builds(Or, inner, inner),
        st.builds(Not, inner),
    ),
    max_leaves=6,
)


def oracle(node: Node, index) -> set[int]:
    """Evaluate node with plain sets, the way the grammar defines it."""
    match node:
        case Term(text):
            found = index.get(text)
            return set(found.doc_ids()) if found else set()
        case And(left, right):
            return oracle(left, index) & oracle(right, index)
        case Or(left, right):
            return oracle(left, index) | oracle(right, index)
        case Not(operand):
            return set(index.documents) - oracle(operand, index)
    raise AssertionError(node)


@given(node=EXPRESSIONS)
def test_evaluate_agrees_with_plain_sets(node, mini_index) -> None:
    assert set(evaluate(node, mini_index).doc_ids()) == oracle(
        node, mini_index
    )


@given(
    st.text(alphabet="aAbB \u0301\u00e9\ufb01\u2026\u00df\u1e9e", max_size=14),
)
def test_snippet_highlights_exactly_the_matching_words(text) -> None:
    # Latin words only and a window wider than the text: every hit is
    # one whole word, so folded it is one of the terms. The offset bug
    # in snippet.py (see test_snippet.py) broke this, for example for
    # "A", U+0301, "ﬁ": the hit was the accent plus the ligature.
    terms = set(tokenize(text))
    parts = make_snippet(text, terms, width=100)
    assert all(fold(shown) in terms for shown, hit in parts if hit)
