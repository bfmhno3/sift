"""Tests for sift.document."""

from datetime import datetime
from pathlib import Path

import pytest

from sift.document import SHANGHAI, Document, parse_datetime
from sift.errors import FrontMatterError

PATH = Path("post.md")
POST = """\
---
title: Hello
published: "2026-02-03 08:00:00 +08:00"
updated: 2026-02-04
tags:
  - a
  - b
category: Notes
series: S
---

# Hello

Some **bold** text.
"""


@pytest.mark.parametrize(
    ("value", "iso"),
    [
        ("2026-01-01 08:00:00 +08:00", "2026-01-01T08:00:00+08:00"),
        ("2026-01-01 08:00 +08:00", "2026-01-01T08:00:00+08:00"),
        ("2026-01-01 08:00:00 +00:00", "2026-01-01T16:00:00+08:00"),
        ("2026-01-01", "2026-01-01T00:00:00+08:00"),
    ],
)
def test_parse_datetime(value: str, iso: str) -> None:
    parsed = parse_datetime(value)
    assert parsed.isoformat() == iso
    assert parsed.tzinfo is SHANGHAI


@pytest.mark.parametrize("value", ["", "yesterday", "2026-13-01", "01/02/26"])
def test_parse_datetime_rejects(value: str) -> None:
    with pytest.raises(ValueError, match="unrecognized date"):
        parse_datetime(value)


def test_from_markdown() -> None:
    doc = Document.from_markdown(7, PATH, POST)
    assert doc.doc_id == 7
    assert doc.title == "Hello"
    assert doc.published == datetime(2026, 2, 3, 8, tzinfo=SHANGHAI)
    assert doc.updated == datetime(2026, 2, 4, tzinfo=SHANGHAI)
    assert doc.tags == ("a", "b")
    assert (doc.category, doc.series) == ("Notes", "S")
    assert doc.body == "\nHello\n\nSome bold text."


def test_optional_fields_default() -> None:
    text = '---\ntitle: T\npublished: "2026-01-01"\n---\nbody'
    doc = Document.from_markdown(0, PATH, text)
    assert doc.updated is None
    assert doc.tags == ()
    assert doc.category is None and doc.series is None


def test_a_single_tag_string_becomes_a_tuple() -> None:
    text = "---\ntitle: T\npublished: 2026-01-01\ntags: solo\n---\n"
    assert Document.from_markdown(0, PATH, text).tags == ("solo",)


def test_document_is_frozen_and_slotted() -> None:
    doc = Document.from_markdown(0, PATH, POST)
    with pytest.raises(AttributeError):
        doc.title = "x"  # type: ignore[misc]
    assert not hasattr(doc, "__dict__")


@pytest.mark.parametrize(
    ("text", "line", "message"),
    [
        ("no front matter", 1, "missing 'title'"),
        ("---\ntitle: T\n---\n", 1, "missing 'published'"),
        ("---\ntitle: T\npublished: nope\n---\n", 3, "unrecognized date"),
        (
            "---\ntitle: T\npublished: 2026-01-01\nupdated: x\n---\n",
            4,
            "unrecognized date",
        ),
        ("---\ntitle: T\nbad line\n---\n", 3, "cannot parse line"),
    ],
)
def test_from_markdown_errors(text: str, line: int, message: str) -> None:
    with pytest.raises(FrontMatterError, match=message) as caught:
        Document.from_markdown(0, PATH, text)
    assert caught.value.line == line
    assert caught.value.path == PATH


def test_mini_documents(mini_docs: list[Document]) -> None:
    assert [d.doc_id for d in mini_docs] == list(range(8))
    assert mini_docs[0].path.name == "bicycle-gears.md"
    assert mini_docs[7].title == "Brewing tea: a short guide"
    assert all(d.published.tzinfo is SHANGHAI for d in mini_docs)
