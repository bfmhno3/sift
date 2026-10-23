"""Tests for sift.storage.manifest: the incremental decisions."""

import os
import shutil
from pathlib import Path

import pytest

from sift.errors import IndexCorruptError, IndexMissingError
from sift.storage.manifest import (
    FileEntry,
    Manifest,
    load_manifest,
    plan_update,
    save_manifest,
    sha256_file,
)


@pytest.fixture
def corpus(tmp_path: Path, mini_root: Path) -> Path:
    root = tmp_path / "posts"
    shutil.copytree(mini_root, root)
    return root


def bump(path: Path, seconds: int = 10) -> None:
    """Move the mtime of path forward."""
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + seconds * 10**9))


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "x.md"
    path.write_bytes(b"abc")
    assert sha256_file(path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_first_plan_numbers_files_in_sorted_order(corpus: Path) -> None:
    plan = plan_update(corpus, None)
    names = sorted(p.name for p in corpus.glob("*.md"))
    assert list(plan.manifest.files) == names
    assert [plan.manifest.files[n].doc_id for n in names] == list(range(8))
    assert plan.manifest.next_doc_id == 8
    assert len(plan.reparse) == 8
    assert plan.removed == []
    assert plan.unchanged == 0


def test_nothing_changed(corpus: Path) -> None:
    first = plan_update(corpus, None).manifest
    plan = plan_update(corpus, first)
    assert plan.reparse == []
    assert plan.removed == []
    assert plan.unchanged == 8
    assert plan.manifest == first


def test_touch_alone_keeps_the_file_out_of_the_reparse(
    corpus: Path,
) -> None:
    first = plan_update(corpus, None).manifest
    target = corpus / "tea-ceremony.md"
    bump(target)
    plan = plan_update(corpus, first)
    assert plan.reparse == []
    assert plan.unchanged == 8
    old = first.files["tea-ceremony.md"]
    new = plan.manifest.files["tea-ceremony.md"]
    assert new.sha256 == old.sha256
    assert new.doc_id == old.doc_id
    assert new.mtime_ns != old.mtime_ns


def test_changed_content_keeps_the_doc_id(corpus: Path) -> None:
    first = plan_update(corpus, None).manifest
    target = corpus / "river-flow.md"
    target.write_text(target.read_text() + "\nmore words\n")
    bump(target)
    plan = plan_update(corpus, first)
    assert [c.relpath for c in plan.reparse] == ["river-flow.md"]
    entry = plan.manifest.files["river-flow.md"]
    assert entry.doc_id == first.files["river-flow.md"].doc_id
    assert entry.sha256 != first.files["river-flow.md"].sha256
    assert plan.unchanged == 7
    assert plan.stale_ids == {entry.doc_id}


def test_new_file_gets_next_doc_id(corpus: Path) -> None:
    first = plan_update(corpus, None).manifest
    (corpus / "aaa-new.md").write_text("---\ntitle: x\n---\n")
    plan = plan_update(corpus, first)
    assert plan.manifest.files["aaa-new.md"].doc_id == 8
    assert plan.manifest.next_doc_id == 9
    assert first.files["bicycle-gears.md"].doc_id == 0


def test_deleted_ids_are_never_reused(corpus: Path) -> None:
    first = plan_update(corpus, None).manifest
    gone = first.files["tea-brewing.md"].doc_id
    (corpus / "tea-brewing.md").unlink()
    second = plan_update(corpus, first)
    assert second.removed == [gone]
    assert "tea-brewing.md" not in second.manifest.files
    assert second.manifest.next_doc_id == 8
    (corpus / "zzz-new.md").write_text("---\ntitle: x\n---\n")
    third = plan_update(corpus, second.manifest)
    assert third.manifest.files["zzz-new.md"].doc_id == 8
    assert gone not in {e.doc_id for e in third.manifest.files.values()}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    manifest = Manifest(
        "corpus/posts",
        5,
        {"b.md": FileEntry("ff", 2, 1), "a/é.md": FileEntry("00", 1, 4)},
    )
    path = tmp_path / "manifest.json"
    save_manifest(path, manifest)
    assert load_manifest(path) == manifest


def test_load_missing(tmp_path: Path) -> None:
    with pytest.raises(IndexMissingError):
        load_manifest(tmp_path / "manifest.json")


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        "{}",
        '{"corpus": "c", "next_doc_id": 1, "files": []}',
        '{"corpus": "c", "next_doc_id": "x", "files": {}}',
        '{"corpus": "c", "next_doc_id": 1, "files": {"a": {"sha256": "1"}}}',
    ],
)
def test_load_corrupt(tmp_path: Path, text: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(text)
    with pytest.raises(IndexCorruptError):
        load_manifest(path)
