"""Tests for sift.frontmatter."""

from pathlib import Path

import pytest

from sift.errors import FrontMatterError
from sift.frontmatter import parse_front_matter


def test_scalars_lists_and_block_scalars() -> None:
    text = (
        'title: "A: b"\n'
        "n: 3\n"
        "flag: true\n"
        "off: false\n"
        "plain: hello world\n"
        "single: 'it''s'\n"
        "inline: [a, \"b c\", 'd']\n"
        "tags:\n"
        "  - x\n"
        "  - y z\n"
        "folded: >-\n"
        "  one\n"
        "  two\n"
    )
    assert parse_front_matter(text) == {
        "title": "A: b",
        "n": 3,
        "flag": True,
        "off": False,
        "plain": "hello world",
        "single": "it's",
        "inline": ["a", "b c", "d"],
        "tags": ["x", "y z"],
        "folded": "one two",
    }


def test_empty_text_is_an_empty_dict() -> None:
    assert parse_front_matter("") == {}
    assert parse_front_matter("\n\n") == {}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("a: [x", "unterminated inline list"),
        ("a: 1\na: 2", "duplicate key 'a'"),
        ("k:\n", "key 'k' has no value"),
        ("  - x", "list item without a key"),
        ("x y", "cannot parse line"),
        ("a: {b}", "unsupported syntax"),
        ("a: b: c", "ambiguous plain string"),
        ('t: "\\q"', r"unsupported escape \\q"),
        ("a: >+\n  x", "unsupported block scalar header"),
        ('a: "x" y', "bad double-quoted string"),
        ("a: 'x' y", "bad single-quoted string"),
        ('a: [a, "b]', "bad inline list"),
        ("k:\nother: 1", "key 'k' has no value"),
    ],
)
def test_malformed_input_raises(text: str, message: str) -> None:
    with pytest.raises(FrontMatterError, match=message):
        parse_front_matter(text)


def test_error_line_is_a_line_of_the_file() -> None:
    path = Path("post.md")
    with pytest.raises(FrontMatterError) as caught:
        parse_front_matter("a: 1\nb c\n", path, first_line=2)
    assert caught.value.line == 3
    assert caught.value.path == path
    assert str(caught.value).startswith("post.md:3: ")


def test_block_scalar_keeps_newlines_with_a_pipe() -> None:
    assert parse_front_matter("t: |-\n  a\n  b\n") == {"t": "a\nb"}
    assert parse_front_matter("t: |\n  a\n") == {"t": "a\n"}


def test_block_scalar_drops_trailing_blank_lines() -> None:
    assert parse_front_matter("t: >-\n  a\n\nnext: 1") == {
        "t": "a",
        "next": 1,
    }
