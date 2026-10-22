"""Tests for sift.corpus."""

import logging
from pathlib import Path

import pytest

from sift.corpus import iter_documents
from sift.errors import FrontMatterError

GOOD = '---\ntitle: T{n}\npublished: "2026-01-0{n} 08:00:00 +08:00"\n---\nx'
BAD = "---\ntitle: T\nthis line is not yaml\n---\n"


def write_posts(root: Path, names_and_texts: dict[str, str]) -> None:
    """Write each file below root."""
    for name, text in names_and_texts.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_documents_come_in_sorted_path_order(tmp_path: Path) -> None:
    write_posts(
        tmp_path,
        {
            "b.md": GOOD.format(n=2),
            "a.md": GOOD.format(n=1),
            "sub/c.md": GOOD.format(n=3),
            "note.txt": "ignored",
        },
    )
    docs = list(iter_documents(tmp_path))
    assert [(d.doc_id, d.path.name) for d in docs] == [
        (0, "a.md"),
        (1, "b.md"),
        (2, "c.md"),
    ]


def test_empty_directory_yields_nothing(tmp_path: Path) -> None:
    assert list(iter_documents(tmp_path)) == []


def test_files_are_read_lazily(tmp_path: Path) -> None:
    write_posts(tmp_path, {"a.md": GOOD.format(n=1), "b.md": BAD})
    stream = iter_documents(tmp_path)
    assert next(stream).doc_id == 0  # b.md is not read yet


def test_bad_files_raise_one_group_at_the_end(tmp_path: Path) -> None:
    write_posts(
        tmp_path,
        {"a.md": BAD, "b.md": GOOD.format(n=2), "c.md": BAD},
    )
    seen = []
    with pytest.raises(ExceptionGroup) as caught:
        for doc in iter_documents(tmp_path):
            seen.append(doc.doc_id)
    assert seen == [1]
    assert caught.value.message == "2 files failed"
    assert all(
        isinstance(e, FrontMatterError) for e in caught.value.exceptions
    )
    assert [e.path.name for e in caught.value.exceptions] == ["a.md", "c.md"]


def test_one_failure_is_worded_in_the_singular(tmp_path: Path) -> None:
    write_posts(tmp_path, {"a.md": BAD})
    with pytest.raises(ExceptionGroup, match=r"1 file failed"):
        list(iter_documents(tmp_path))


def test_keep_going_logs_and_skips(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_posts(tmp_path, {"a.md": BAD, "b.md": GOOD.format(n=2)})
    with caplog.at_level(logging.WARNING, logger="sift.corpus"):
        docs = list(iter_documents(tmp_path, keep_going=True))
    assert [d.doc_id for d in docs] == [1]  # the skipped id stays unused
    assert len(caplog.records) == 1
    assert "a.md:3" in caplog.text


def test_mini_corpus_has_no_bad_file(mini_root: Path) -> None:
    assert len(list(iter_documents(mini_root))) == 8


CORPUS = Path(__file__).parent.parent / "corpus" / "posts"


@pytest.mark.slow
@pytest.mark.skipif(not CORPUS.is_dir(), reason="run `make corpus` first")
def test_full_corpus_parses_strictly() -> None:
    docs = list(iter_documents(CORPUS))
    assert len(docs) == 123
    assert len({d.title for d in docs}) > 100
