"""Tests for sift.markdown."""

import pytest

from sift.markdown import split_front_matter, strip_markdown


@pytest.mark.parametrize(
    ("text", "front", "body"),
    [
        ("---\na: 1\n---\nbody\n", "a: 1\n", "body\n"),
        ("---\n---\nbody", "", "body"),
        ("no front matter\n", "", "no front matter\n"),
        ("", "", ""),
        ("---\nnever closed\n", "", "---\nnever closed\n"),
        ("---  \na: 1\n---  \nx", "a: 1\n", "x"),
        ("text\n---\na: 1\n---\n", "", "text\n---\na: 1\n---\n"),
    ],
    ids=[
        "basic",
        "empty",
        "none",
        "empty-text",
        "unclosed",
        "trailing",
        "late",
    ],
)
def test_split_front_matter(text: str, front: str, body: str) -> None:
    assert split_front_matter(text) == (front, body)


def test_split_keeps_every_byte_of_the_body() -> None:
    text = "---\nt: x\n---\n---\nsecond rule stays\n"
    assert split_front_matter(text) == ("t: x\n", "---\nsecond rule stays\n")


@pytest.mark.parametrize(
    ("markdown", "plain"),
    [
        ("# Title", "Title"),
        ("### Deep heading", "Deep heading"),
        ("**bold** and __bold__", "bold and bold"),
        ("*it* and _it_", "it and it"),
        ("~~gone~~", "gone"),
        ("[text](https://example.com/x)", "text"),
        ("before ![alt](img.png) after", "before  after"),
        ("<https://example.com>", "https://example.com"),
        ("a <b>tag</b> b", "a tag b"),
        ("> quoted line", "quoted line"),
        ("snake_case_name stays", "snake_case_name stays"),
        ("2 * 3 * 4", "2 * 3 * 4"),
    ],
)
def test_strip_inline_syntax(markdown: str, plain: str) -> None:
    assert strip_markdown(markdown) == plain


def test_fence_markers_go_but_the_code_stays() -> None:
    body = "text\n```python\nx = 1  # **not bold**\n```\nmore"
    assert strip_markdown(body) == "text\nx = 1  # **not bold**\nmore"


def test_tilde_fence_is_a_fence_too() -> None:
    assert strip_markdown("~~~\n# not a heading\n~~~") == "# not a heading"


def test_table_rule_row_is_dropped_and_pipes_become_spaces() -> None:
    table = "| a | b |\n| --- | :---: |\n| 1 | 2 |"
    lines = strip_markdown(table).splitlines()
    assert [line.split() for line in lines] == [["a", "b"], ["1", "2"]]


def test_inline_code_keeps_its_text() -> None:
    assert strip_markdown("call `parse()` now") == "call parse() now"


@pytest.mark.xfail(
    strict=True,
    reason="known gap: the HTML-tag pass eats <u8> inside inline code",
)
def test_inline_code_with_angle_brackets() -> None:
    assert strip_markdown("use `Vec<u8>` here") == "use Vec<u8> here"
