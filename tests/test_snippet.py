"""Tests for sift.snippet."""

import pytest

from sift.analysis.tokenize import fold
from sift.snippet import html, make_snippet, render_html, render_plain

LONG = "word " * 100 + "needle " + "word " * 100


def test_hit_is_marked_and_edges_are_cut() -> None:
    parts = make_snippet(LONG, {"needle"}, width=40)
    assert parts[0] == ("…", False)
    assert parts[-1] == ("…", False)
    assert ("needle", True) in parts
    shown = sum(len(text) for text, _ in parts if text != "…")
    assert shown <= 40


def test_no_hit_shows_the_start_of_the_text() -> None:
    parts = make_snippet(LONG, {"zebra"}, width=20)
    assert parts == [("word " * 4, False), ("…", False)]


def test_short_text_has_no_ellipsis() -> None:
    assert make_snippet("a fox", {"fox"}) == [("a ", False), ("fox", True)]


def test_empty_text_and_empty_terms() -> None:
    assert make_snippet("", {"x"}) == []
    assert make_snippet("abc", set()) == [("abc", False)]


def test_window_goes_to_the_densest_cluster() -> None:
    text = "fox " + "x " * 60 + "fox fox fox " + "y " * 60
    parts = make_snippet(text, {"fox"}, width=30)
    assert sum(hit for _, hit in parts) >= 3


def test_whitespace_runs_are_collapsed() -> None:
    parts = make_snippet("a  \n\n  b   fox", {"fox"})
    assert render_plain(parts) == "a b [fox]"


def test_hits_are_found_after_nfkc_changes_lengths() -> None:
    # "…" folds to three dots, so folded offsets drift from str ones.
    text = "wait… then fox"
    assert render_plain(make_snippet(text, {"fox"})) == "wait… then [fox]"


def test_cjk_bigram_hits_merge_into_one_span() -> None:
    parts = make_snippet("前面 全文搜索 后面", {"全文", "文搜", "搜索"})
    assert ("全文搜索", True) in parts


def test_text_is_returned_in_order_without_loss() -> None:
    text = "alpha beta gamma delta"
    parts = make_snippet(text, {"beta", "delta"})
    assert "".join(t for t, _ in parts) == text


def test_html_escapes_values_not_static_text() -> None:
    user = "<script>&"
    assert html(t"<p>{user}</p>") == "<p>&lt;script&gt;&amp;</p>"


def test_html_conversion_and_format_spec() -> None:
    word = "a<b"
    assert html(t"{word!r}") == "&#x27;a&lt;b&#x27;"
    assert html(t"{3.14159:.2f}") == "3.14"


def test_html_renders_nested_templates_once() -> None:
    inner = t"<b>{'x&y'}</b>"
    assert html(t"<p>{inner}</p>") == "<p><b>x&amp;y</b></p>"


def test_render_html_wraps_hits() -> None:
    parts = [("1 < 2 ", False), ("fox", True), (" & co", False)]
    assert render_html(parts) == "1 &lt; 2 <mark>fox</mark> &amp; co"


@pytest.mark.parametrize(
    ("parts", "plain"),
    [
        ([], ""),
        ([("a", False)], "a"),
        ([("a", True), ("b", False), ("c", True)], "[a]b[c]"),
    ],
)
def test_render_plain(parts: list[tuple[str, bool]], plain: str) -> None:
    assert render_plain(parts) == plain


def test_equal_length_does_not_mean_equal_offsets() -> None:
    # Regression, found by hypothesis
    # (test_snippet_highlights_exactly_the_matching_words): "A" plus a
    # combining accent composes to one character and the ligature "ﬁ"
    # expands to two, so fold(text) has the length of text and yet
    # every offset after the accent moves. The hit must be "fi", not
    # the accent.
    text = "A\u0301\ufb01"
    parts = make_snippet(text, {"fi"})
    assert [t for t, hit in parts if hit] == ["fi"]
    assert render_plain(parts) == "á[fi]"


def test_sharp_s_with_accent_is_tokenized_once() -> None:
    # Regression, found by a brute-force sweep after the fix above:
    # when the per-character folds do not add up (a combining mark
    # after a sharp s), the folded text is shown, and tokenizing that
    # copy folded it a second time ("ss" plus U+0301 composes).
    text = "a\u0301\u00df\u0301a"
    parts = make_snippet(text, {"a", "ss"})
    assert all(fold(shown) in {"a", "ss"} for shown, hit in parts if hit)
    assert "[\u0301]" not in render_plain(parts)


def test_ligature_after_ascii_text_still_maps_back() -> None:
    parts = make_snippet("a \ufb01sh \u00e9", {"fish"})
    assert render_plain(parts) == "a [\ufb01sh] \u00e9"
