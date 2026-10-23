"""Tests for sift.storage.db: rows, the query log, injection safety."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from sift.document import Document
from sift.errors import IndexCorruptError, SiftError
from sift.storage.db import (
    DocumentRow,
    MetaRow,
    QueryLogRow,
    load_document,
    load_documents,
    log_query,
    open_db,
    recent_queries,
    replace_documents,
    session_scope,
)

SHA = "0" * 64
NAMES = ["mixed", "nfkc"]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "sift.db"


def make_doc(doc_id: int, **changes: object) -> Document:
    fields: dict[str, object] = {
        "doc_id": doc_id,
        "path": Path(f"posts/p{doc_id}.md"),
        "title": f"Title {doc_id} 标题",
        "published": datetime(
            2026, 1, 2, 8, 0, tzinfo=timezone(timedelta(hours=8))
        ),
        "updated": None,
        "tags": ("a", "标签"),
        "category": "Note",
        "series": None,
        "body": "body 正文",
    }
    fields.update(changes)
    return Document(**fields)  # type: ignore[arg-type]


def test_open_db_creates_the_tables(db: Path) -> None:
    maker = open_db(db)
    maker.kw["bind"].dispose()
    con = sqlite3.connect(db)
    names = {
        name
        for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    con.close()
    assert names == {"documents", "meta", "query_log"}


def test_documents_roundtrip_keeps_every_field(db: Path) -> None:
    docs = [
        make_doc(0),
        make_doc(
            3,
            updated=datetime(2026, 2, 3, 9, 30, tzinfo=UTC),
            series="S",
            category=None,
            tags=(),
        ),
    ]
    digests = {0: SHA, 3: "f" * 64}
    replace_documents(db, NAMES, docs, digests)
    names, loaded = load_documents(db)
    assert names == NAMES
    assert list(loaded.values()) == docs
    assert loaded[3].updated is not None
    assert loaded[3].updated.utcoffset() == timedelta(hours=8)


def test_row_keeps_tags_as_json_text_and_the_digest(db: Path) -> None:
    replace_documents(db, NAMES, [make_doc(0)], {0: SHA})
    con = sqlite3.connect(db)
    tags, sha = con.execute("SELECT tags, sha256 FROM documents").fetchone()
    con.close()
    assert json.loads(tags) == ["a", "标签"]
    assert sha == SHA


def test_replace_with_drop_keeps_the_other_rows(db: Path) -> None:
    docs = [make_doc(i) for i in range(4)]
    replace_documents(db, NAMES, docs, dict.fromkeys(range(4), SHA))
    fresh = make_doc(1, title="New")
    replace_documents(db, NAMES, [fresh], {1: "1" * 64}, drop={1, 3})
    _, loaded = load_documents(db)
    assert sorted(loaded) == [0, 1, 2]
    assert loaded[1].title == "New"


def test_replace_without_drop_deletes_everything_first(db: Path) -> None:
    docs = [make_doc(i) for i in range(3)]
    replace_documents(db, NAMES, docs, dict.fromkeys(range(3), SHA))
    replace_documents(db, ["mixed"], [make_doc(7)], {7: SHA})
    names, loaded = load_documents(db)
    assert names == ["mixed"]
    assert sorted(loaded) == [7]


def test_failed_write_rolls_back(db: Path) -> None:
    replace_documents(db, NAMES, [make_doc(0)], {0: SHA})
    with pytest.raises(IntegrityError):
        replace_documents(
            db,
            NAMES,
            [make_doc(1), make_doc(1)],
            {1: SHA},
            drop={0},
        )
    _, loaded = load_documents(db)
    assert sorted(loaded) == [0]


def test_load_missing_file_is_corrupt(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="missing"):
        load_documents(tmp_path / "nope.db")
    assert not (tmp_path / "nope.db").exists()


def test_load_garbage_is_corrupt(db: Path) -> None:
    db.write_bytes(b"not sqlite at all" * 50)
    with pytest.raises(IndexCorruptError, match="bad database"):
        load_documents(db)


def test_load_malformed_row_is_corrupt(db: Path) -> None:
    replace_documents(db, NAMES, [make_doc(0)], {0: SHA})
    con = sqlite3.connect(db)
    con.execute("UPDATE documents SET published = 'yesterday'")
    con.commit()
    con.close()
    with pytest.raises(IndexCorruptError):
        load_documents(db)


def test_query_log_appends_in_order(db: Path) -> None:
    for number in range(3):
        log_query(db, f"q{number}", number, number / 2)
    rows = recent_queries(db)
    assert [r.query for r in rows] == ["q2", "q1", "q0"]
    assert [r.id for r in rows] == [3, 2, 1]
    assert (rows[0].total, rows[0].took_ms) == (2, 1.0)


def test_query_log_limit(db: Path) -> None:
    for number in range(15):
        log_query(db, f"q{number}", 0, 0.1)
    assert len(recent_queries(db)) == 10
    assert len(recent_queries(db, 3)) == 3
    assert recent_queries(db, 3)[0].query == "q14"


def test_query_log_time_is_aware_utc(db: Path) -> None:
    before = datetime.now(UTC)
    log_query(db, "q", 0, 0.0)
    after = datetime.now(UTC)
    (row,) = recent_queries(db)
    assert row.at.tzinfo is UTC
    assert before - timedelta(seconds=1) <= row.at <= after


def test_naive_log_time_is_refused(db: Path) -> None:
    row = QueryLogRow(at=datetime(2026, 1, 1), query="q", total=0, took_ms=0)
    with pytest.raises(StatementError, match="naive"), session_scope(db) as s:
        s.add(row)


def test_recent_queries_of_a_missing_database(tmp_path: Path) -> None:
    assert recent_queries(tmp_path / "none.db") == []


def test_log_is_not_touched_by_replace_documents(db: Path) -> None:
    log_query(db, "kept", 1, 1.0)
    replace_documents(db, NAMES, [make_doc(0)], {0: SHA})
    assert [r.query for r in recent_queries(db)] == ["kept"]


def test_unwritable_log_raises_sift_error(tmp_path: Path) -> None:
    with pytest.raises(SiftError, match="cannot log the query"):
        log_query(tmp_path / "no" / "such" / "dir.db", "q", 0, 0.0)


def test_unreadable_log_raises_sift_error(db: Path) -> None:
    db.write_bytes(b"not sqlite at all" * 50)
    with pytest.raises(SiftError, match="cannot read the query log"):
        recent_queries(db)


HOSTILE = [
    "'; DROP TABLE query_log; --",
    "x' OR '1'='1",
    'robert"); DELETE FROM documents; --',
    "100% sure_ \\ \x00 end",
    "'" * 5,
]


@pytest.mark.parametrize("query", HOSTILE)
def test_hostile_queries_are_stored_verbatim(db: Path, query: str) -> None:
    replace_documents(db, NAMES, [make_doc(0)], {0: SHA})
    log_query(db, "harmless", 1, 0.1)
    log_query(db, query, 0, 0.1)
    assert [r.query for r in recent_queries(db)] == [query, "harmless"]
    names, loaded = load_documents(db)
    assert sorted(loaded) == [0]


def test_hostile_document_fields_are_data(db: Path) -> None:
    title = "'); DROP TABLE documents; --"
    replace_documents(db, NAMES, [make_doc(0, title=title)], {0: SHA})
    _, loaded = load_documents(db)
    assert loaded[0].title == title
    with session_scope(db) as session:
        found = session.scalars(
            select(DocumentRow).where(DocumentRow.title == title)
        ).all()
        assert len(found) == 1
        assert session.get(MetaRow, "pipeline") is not None


def test_load_document_reads_one_row(db: Path) -> None:
    docs = [make_doc(i) for i in range(3)]
    replace_documents(db, NAMES, docs, dict.fromkeys(range(3), SHA))
    assert load_document(db, 1) == docs[1]
    assert load_document(db, 9) is None


def test_load_document_of_a_bad_database(db: Path, tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="missing"):
        load_document(tmp_path / "nope.db", 0)
    db.write_bytes(b"not sqlite at all" * 50)
    with pytest.raises(IndexCorruptError, match="bad database"):
        load_document(db, 0)
