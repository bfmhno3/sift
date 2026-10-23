"""Tests for sift.storage.store: update, open and search the index."""

import json
import os
import shutil
from pathlib import Path

import pytest

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.errors import IndexCorruptError, IndexMissingError, SiftError
from sift.index import IndexWriter, InvertedIndex
from sift.search import Searcher
from sift.storage.store import (
    DOCS,
    MANIFEST,
    SEGMENT,
    load_docs,
    open_index,
    update_index,
)

NAMES = ("mixed", "nfkc", "stopwords")
QUERIES = [
    "chain",
    "tea AND brewing",
    '"bicycle chain"',
    "river OR compiler",
    "tag:tea",
    "title:river",
    "compil*",
    "bridge -river",
    "编译",
]


@pytest.fixture
def corpus(tmp_path: Path, mini_root: Path) -> Path:
    root = tmp_path / "posts"
    shutil.copytree(mini_root, root)
    return root


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    return tmp_path / "idx"


def edit(path: Path, extra: str) -> None:
    """Append text and move the mtime forward."""
    stat = path.stat()
    path.write_text(path.read_text() + extra, encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**10))


def snapshot(directory: Path) -> tuple:
    """Return everything an index holds, for comparing two indexes."""
    with open_index(directory) as index:
        return (
            index.pipeline_names,
            index.documents,
            index.segment.doc_lens,
            dict(index.segment.iter_postings()),
        )


def test_full_build_writes_three_files(corpus: Path, index_dir: Path) -> None:
    report = update_index(corpus, index_dir, NAMES)
    assert (report.full, report.parsed, report.unchanged) == (True, 8, 0)
    assert report.documents == 8
    assert sorted(p.name for p in index_dir.iterdir()) == [
        DOCS,
        MANIFEST,
        SEGMENT,
    ]
    assert report.size == (index_dir / SEGMENT).stat().st_size


def test_search_matches_the_in_memory_index(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    pipeline = build_pipeline(NAMES)
    memory = InvertedIndex()
    with IndexWriter(memory, pipeline) as writer:
        for doc in iter_documents(corpus):
            writer.add(doc)
    expected = Searcher(memory, pipeline=pipeline)
    with open_index(index_dir) as index:
        got = Searcher(index, pipeline=build_pipeline(index.pipeline_names))
        for query in QUERIES:
            a, b = expected.search(query), got.search(query)
            assert (a.total, [(h.doc_id, h.score) for h in a.hits]) == (
                b.total,
                [(h.doc_id, h.score) for h in b.hits],
            ), query
            assert [h.snippet for h in a.hits] == [h.snippet for h in b.hits]
        assert len(index) == len(memory)
        assert index.avg_doc_len == memory.avg_doc_len
        assert index.title_index == memory.title_index


def test_second_run_changes_nothing(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    before = (index_dir / SEGMENT).read_bytes()
    inode = (index_dir / SEGMENT).stat().st_ino
    report = update_index(corpus, index_dir, NAMES)
    assert (report.full, report.parsed, report.unchanged) == (False, 0, 8)
    assert (index_dir / SEGMENT).read_bytes() == before
    assert (index_dir / SEGMENT).stat().st_ino == inode


def test_incremental_reparses_only_the_changed_file(
    corpus: Path, index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    update_index(corpus, index_dir, NAMES)
    edit(corpus / "river-flow.md", "\nzymurgy zymurgy\n")
    parsed = []
    original = Path.read_text

    def spy(self: Path, *args: object, **kwargs: object) -> str:
        parsed.append(self.name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    report = update_index(corpus, index_dir, NAMES)
    monkeypatch.undo()
    assert (report.full, report.parsed, report.unchanged) == (False, 1, 7)
    assert [n for n in parsed if n.endswith(".md")] == ["river-flow.md"]
    with open_index(index_dir) as index:
        assert [p.tf for p in index["zymurgy"]] == [2]


def test_incremental_equals_full_rebuild(
    corpus: Path, index_dir: Path, tmp_path: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    edit(corpus / "river-flow.md", "\nzymurgy zymurgy\n")
    edit(corpus / "tea-brewing.md", "\nquux\n")
    update_index(corpus, index_dir, NAMES)
    fresh = tmp_path / "fresh"
    update_index(corpus, fresh, NAMES, full=True)
    assert snapshot(index_dir) == snapshot(fresh)


def test_changed_file_loses_its_old_terms(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    target = corpus / "tea-brewing.md"
    stat = target.stat()
    target.write_text(
        "---\ntitle: Replaced\npublished: 2026-02-01\n---\nonlyword\n"
    )
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**10))
    update_index(corpus, index_dir, NAMES)
    with open_index(index_dir) as index:
        assert "onlyword" in index
        assert index.documents[6].title == "Replaced"
        assert index.documents[6].path == target
        assert index["onlyword"].doc_ids() == [6]
        assert all(
            6 not in plist.doc_ids()
            for term, plist in index.segment.iter_postings()
            if term != "onlyword"
        )


def test_deleted_file_and_new_file(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    with open_index(index_dir) as index:
        gone = next(
            d.doc_id
            for d in index.documents.values()
            if "river-flow" in str(d.path)
        )
    (corpus / "river-flow.md").unlink()
    (corpus / "new-post.md").write_text(
        "---\ntitle: Fresh\npublished: 2026-03-01\n---\nuniqueword\n"
    )
    report = update_index(corpus, index_dir, NAMES)
    assert (report.parsed, report.removed, report.documents) == (1, 1, 8)
    with open_index(index_dir) as index:
        assert gone not in index.documents
        assert index["uniqueword"].doc_ids() == [8]
        assert index.segment.doc_len(gone) == 0
        assert all(
            gone not in plist.doc_ids()
            for _, plist in index.segment.iter_postings()
        )
        assert index.n_docs == 8


def test_pipeline_change_rebuilds(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    report = update_index(corpus, index_dir, ("mixed", "nfkc"))
    assert (report.full, report.parsed) == (True, 8)
    with open_index(index_dir) as index:
        assert index.pipeline_names == ("mixed", "nfkc")


def test_full_flag_rebuilds(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    report = update_index(corpus, index_dir, NAMES, full=True)
    assert (report.full, report.parsed) == (True, 8)


def test_corrupt_index_is_rebuilt(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    (index_dir / SEGMENT).write_bytes(b"garbage")
    report = update_index(corpus, index_dir, NAMES)
    assert (report.full, report.parsed) == (True, 8)
    open_index(index_dir).close()


def test_compressed_segment(corpus: Path, index_dir: Path) -> None:
    plain = update_index(corpus, index_dir, NAMES)
    packed = update_index(corpus, index_dir, NAMES, full=True, compress=True)
    assert packed.size != plain.size
    with open_index(index_dir) as index:
        assert index.segment.compressed
        assert index["chain"].doc_ids()


def test_bad_front_matter_writes_nothing(
    corpus: Path, index_dir: Path
) -> None:
    (corpus / "broken.md").write_text("---\ntitle: [oops\n---\nx\n")
    with pytest.raises(ExceptionGroup) as caught:
        update_index(corpus, index_dir, NAMES)
    assert caught.value.message == "1 file failed"
    assert not (index_dir / SEGMENT).exists()


def test_missing_corpus(tmp_path: Path, index_dir: Path) -> None:
    with pytest.raises(SiftError, match="no corpus at"):
        update_index(tmp_path / "nope", index_dir, NAMES)


def test_open_missing_index(tmp_path: Path) -> None:
    with pytest.raises(IndexMissingError, match="run 'sift index' first"):
        open_index(tmp_path / "nope")


def test_open_without_docs_file(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    (index_dir / DOCS).unlink()
    with pytest.raises(IndexCorruptError, match="docs"):
        open_index(index_dir)


def test_docs_file_roundtrip(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    names, documents = load_docs(index_dir / DOCS)
    assert names == list(NAMES)
    assert list(documents.values()) == list(iter_documents(corpus))


def test_malformed_docs_file(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    (index_dir / DOCS).write_text(json.dumps({"pipeline": []}))
    with pytest.raises(IndexCorruptError):
        open_index(index_dir)


def test_doc_without_length_slot_is_corrupt(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    data = json.loads((index_dir / DOCS).read_text())
    data["documents"][0]["doc_id"] = 99
    (index_dir / DOCS).write_text(json.dumps(data))
    with pytest.raises(IndexCorruptError, match="length slot"):
        open_index(index_dir)


def test_no_temp_files_are_left_behind(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    update_index(corpus, index_dir, NAMES, full=True)
    assert len(list(index_dir.iterdir())) == 3


def test_incremental_can_switch_compression(
    corpus: Path, index_dir: Path, tmp_path: Path
) -> None:
    update_index(corpus, index_dir, NAMES, compress=True)
    edit(corpus / "river-flow.md", "\nzymurgy\n")
    update_index(corpus, index_dir, NAMES, compress=False)
    fresh = tmp_path / "fresh"
    update_index(corpus, fresh, NAMES, full=True)
    assert snapshot(index_dir) == snapshot(fresh)
    assert (index_dir / SEGMENT).read_bytes() == (fresh / SEGMENT).read_bytes()


def test_incremental_segment_is_byte_identical_to_a_full_build(
    corpus: Path, index_dir: Path, tmp_path: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    edit(corpus / "bicycle-gears.md", "\nzymurgy chain\n")
    update_index(corpus, index_dir, NAMES)
    fresh = tmp_path / "fresh"
    update_index(corpus, fresh, NAMES, full=True)
    assert (index_dir / SEGMENT).read_bytes() == (fresh / SEGMENT).read_bytes()
