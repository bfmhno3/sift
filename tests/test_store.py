"""Tests for sift.storage.store: update, open and search the index."""

import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import delete, select, update

import sift.storage.db
from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.errors import IndexCorruptError, IndexMissingError, SiftError
from sift.index import IndexWriter, InvertedIndex
from sift.search import Searcher
from sift.storage.db import (
    DocumentRow,
    MetaRow,
    load_documents,
    log_query,
    recent_queries,
    session_scope,
)
from sift.storage.manifest import sha256_file
from sift.storage.store import (
    DB,
    MANIFEST,
    SEGMENT,
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
        MANIFEST,
        SEGMENT,
        DB,
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


def digests(directory: Path) -> dict[int, str]:
    """Return the sha256 stored for every document row."""
    with session_scope(directory / DB) as session:
        rows = session.execute(select(DocumentRow.doc_id, DocumentRow.sha256))
        return dict(rows.tuples().all())


def test_open_without_database(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    (index_dir / DB).unlink()
    with pytest.raises(IndexCorruptError, match="sift.db"):
        open_index(index_dir)


def test_database_roundtrip(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    names, documents = load_documents(index_dir / DB)
    assert names == list(NAMES)
    assert list(documents.values()) == list(iter_documents(corpus))


def test_database_without_pipeline_is_corrupt(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    with session_scope(index_dir / DB) as session:
        session.execute(delete(MetaRow))
    with pytest.raises(IndexCorruptError, match="no pipeline"):
        open_index(index_dir)


def test_doc_without_length_slot_is_corrupt(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    with session_scope(index_dir / DB) as session:
        session.execute(
            update(DocumentRow)
            .where(DocumentRow.doc_id == 0)
            .values(doc_id=99)
        )
    with pytest.raises(IndexCorruptError, match="length slot"):
        open_index(index_dir)


def test_garbage_database_is_replaced_on_rebuild(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    (index_dir / DB).write_bytes(b"this is not a database" * 100)
    with pytest.raises(IndexCorruptError):
        open_index(index_dir)
    report = update_index(corpus, index_dir, NAMES)
    assert (report.full, report.parsed) == (True, 8)
    open_index(index_dir).close()
    corrupt = index_dir / "sift.db.corrupt"
    assert corrupt.read_bytes().startswith(b"this is not")


def test_older_corrupt_file_is_replaced(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    corrupt = index_dir / "sift.db.corrupt"
    corrupt.write_bytes(b"old")
    (index_dir / DB).write_bytes(b"newer garbage" * 100)
    update_index(corpus, index_dir, NAMES)
    assert corrupt.read_bytes().startswith(b"newer garbage")


def test_rebuild_keeps_the_query_log(corpus: Path, index_dir: Path) -> None:
    update_index(corpus, index_dir, NAMES)
    log_query(index_dir / DB, "chain", 1, 0.5)
    update_index(corpus, index_dir, NAMES, full=True)
    assert [r.query for r in recent_queries(index_dir / DB)] == ["chain"]


def test_incremental_update_rewrites_only_the_changed_rows(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    before = digests(index_dir)
    edit(corpus / "river-flow.md", "\nzymurgy zymurgy\n")
    (corpus / "tea-brewing.md").unlink()
    update_index(corpus, index_dir, NAMES)
    after = digests(index_dir)
    assert after.keys() == before.keys() - {6}
    changed = {i for i in after if after[i] != before[i]}
    assert len(changed) == 1
    _, documents = load_documents(index_dir / DB)
    (edited,) = [d for d in documents.values() if "river-flow" in str(d.path)]
    assert "zymurgy zymurgy" in edited.body
    assert after[edited.doc_id] == sha256_file(corpus / "river-flow.md")


def test_database_equals_a_full_build_after_updates(
    corpus: Path, index_dir: Path, tmp_path: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    edit(corpus / "river-flow.md", "\nzymurgy\n")
    edit(corpus / "tea-brewing.md", "\nquux\n")
    update_index(corpus, index_dir, NAMES)
    fresh = tmp_path / "fresh"
    update_index(corpus, fresh, NAMES, full=True)
    assert load_documents(index_dir / DB) == load_documents(fresh / DB)
    assert digests(index_dir) == digests(fresh)


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


def test_same_corpus_spelled_differently_is_not_rebuilt(
    corpus: Path, index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    update_index(corpus.resolve(), index_dir, NAMES)
    monkeypatch.chdir(corpus.parent)
    report = update_index(Path("posts"), index_dir, NAMES)
    assert (report.full, report.parsed, report.unchanged) == (False, 0, 8)
    report = update_index(corpus / ".." / "posts", index_dir, NAMES)
    assert report.full is False


def test_read_only_database_is_not_renamed(
    corpus: Path, index_dir: Path
) -> None:
    update_index(corpus, index_dir, NAMES)
    db = index_dir / DB
    before = db.read_bytes()
    db.chmod(0o444)
    try:
        if os.access(db, os.W_OK):
            pytest.skip("running as root: chmod 444 does not stop writes")
        with pytest.raises(SiftError, match="database is read-only"):
            update_index(corpus, index_dir, NAMES, full=True)
    finally:
        db.chmod(0o644)
    assert db.read_bytes() == before
    assert not (index_dir / "sift.db.corrupt").exists()


def test_locked_database_is_not_renamed(
    corpus: Path,
    index_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_index(corpus, index_dir, NAMES)
    monkeypatch.setattr(sift.storage.db, "BUSY_TIMEOUT", 0.05)
    other = sqlite3.connect(index_dir / DB, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(SiftError, match="database is locked"):
            update_index(corpus, index_dir, NAMES, full=True)
    finally:
        other.execute("ROLLBACK")
        other.close()
    assert not (index_dir / "sift.db.corrupt").exists()
    names, documents = load_documents(index_dir / DB)
    assert len(documents) == 8
