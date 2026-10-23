"""The SQLite database of an index: documents and the query log.

``.sift/sift.db`` holds three tables, declared with the SQLAlchemy 2.0
ORM:

``documents``
    One ``DocumentRow`` per live post: the metadata and the stripped
    text that ``sift show`` and the snippets need, plus the sha256 of
    the source file.
``meta``
    Small facts about the index, today only the analysis pipeline
    names (``pipeline``), stored as a JSON list.
``query_log``
    One ``QueryLogRow`` per ``sift search`` that was not run with
    ``--no-log``. Rows are only ever appended.

The postings stay in ``segment.sft``: they are read as one block of
bytes and are never queried by column, so a table would only cost.

The manifest stays ``manifest.json`` on purpose. It is written last and
replaced atomically, so it doubles as the commit record of an update:
a crash between the segment and the database leaves the old manifest,
and the next ``sift index`` redoes the work. Moving it into the
database would add a table and a second reader for the same
all-or-nothing file, and its mtimes are compared in plain Python
anyway.

Every function takes the database path and opens its own engine for
the duration of the call, so no connection outlives a command.
"""

import json
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from sqlalchemy import (
    JSON,
    DateTime,
    Dialect,
    String,
    TypeDecorator,
    create_engine,
    delete,
    select,
)
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from sift.document import SHANGHAI, Document
from sift.errors import IndexCorruptError, SiftError

PIPELINE_KEY = "pipeline"


class UtcDateTime(TypeDecorator[datetime]):
    """A DateTime that SQLite stores as UTC and returns as UTC.

    SQLite has no time zone type, and SQLAlchemy would silently drop
    the tzinfo of an aware datetime. This decorator converts to UTC on
    the way in, rejects naive values, and attaches UTC on the way out.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Return value as a naive UTC datetime."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: give the time zone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Return the stored naive value as an aware UTC datetime."""
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Declarative base of the Sift tables."""


class DocumentRow(Base):
    """One indexed post. ``tags`` is a JSON list, dates are ISO 8601."""

    __tablename__ = "documents"

    doc_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    path: Mapped[str]
    title: Mapped[str]
    published: Mapped[str]
    updated: Mapped[str | None]
    category: Mapped[str | None]
    series: Mapped[str | None]
    tags: Mapped[list[str]] = mapped_column(JSON)
    body: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))

    @classmethod
    def from_document(cls, doc: Document, sha256: str) -> Self:
        """Return the row for doc, whose source file hashes to sha256."""
        return cls(
            doc_id=doc.doc_id,
            path=str(doc.path),
            title=doc.title,
            published=doc.published.isoformat(),
            updated=doc.updated.isoformat() if doc.updated else None,
            category=doc.category,
            series=doc.series,
            tags=list(doc.tags),
            body=doc.body,
            sha256=sha256,
        )

    def to_document(self) -> Document:
        """Return the Document this row stores."""
        return Document(
            doc_id=self.doc_id,
            path=Path(self.path),
            title=self.title,
            published=_local(self.published),
            updated=None if self.updated is None else _local(self.updated),
            tags=tuple(map(str, self.tags)),
            category=self.category,
            series=self.series,
            body=self.body,
        )


class MetaRow(Base):
    """A fact about the index: a key and a JSON text value."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class QueryLogRow(Base):
    """One logged search; ``at`` is aware UTC."""

    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UtcDateTime)
    query: Mapped[str]
    total: Mapped[int]
    took_ms: Mapped[float]


def _local(text: str) -> datetime:
    """Parse an ISO 8601 string into Asia/Shanghai time."""
    return datetime.fromisoformat(text).astimezone(SHANGHAI)


def open_db(path: Path) -> sessionmaker[Session]:
    """Open the database at path, creating the tables that are missing.

    The file is created if it does not exist. Rows are not expired on
    commit, so they stay readable after their session closed. Call
    ``maker.kw["bind"].dispose()`` when done; most code should use
    ``session_scope`` instead.
    """
    engine = create_engine(URL.create("sqlite", database=str(path)))
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(path: Path) -> Iterator[Session]:
    """Yield a session on the database at path.

    The transaction commits when the block ends and rolls back when it
    raises; the engine is disposed either way.
    """
    maker = open_db(path)
    try:
        with maker.begin() as session:
            yield session
    finally:
        maker.kw["bind"].dispose()


def replace_documents(
    path: Path,
    pipeline: Sequence[str],
    fresh: Iterable[Document],
    digests: Mapping[int, str],
    *,
    drop: Collection[int] | None = None,
) -> None:
    """Store the pipeline names and the fresh documents, in one transaction.

    drop lists the doc ids to delete first (changed and deleted
    files); None deletes every document. digests maps a doc id to the
    sha256 of its file. The query log is never touched.
    """
    with session_scope(path) as session:
        if drop is None:
            session.execute(delete(DocumentRow))
        else:
            session.execute(
                delete(DocumentRow).where(DocumentRow.doc_id.in_(drop))
            )
        session.add_all(
            DocumentRow.from_document(doc, digests[doc.doc_id])
            for doc in fresh
        )
        session.merge(MetaRow(key=PIPELINE_KEY, value=json.dumps(pipeline)))


def load_documents(path: Path) -> tuple[list[str], dict[int, Document]]:
    """Read ``(pipeline names, documents by doc id)`` from the database.

    Raise IndexCorruptError if the file is missing, is not a database,
    or lacks the pipeline fact or holds a malformed row.
    """
    if not path.is_file():
        raise IndexCorruptError(f"{path}: bad database: file is missing")
    try:
        with session_scope(path) as session:
            value = session.get(MetaRow, PIPELINE_KEY)
            if value is None:
                raise ValueError("no pipeline recorded")
            names = [str(name) for name in json.loads(value.value)]
            rows = session.scalars(select(DocumentRow).order_by("doc_id"))
            documents = {row.doc_id: row.to_document() for row in rows}
    except (SQLAlchemyError, ValueError, TypeError) as error:
        raise IndexCorruptError(f"{path}: bad database: {error}") from None
    return names, documents


def log_query(path: Path, query: str, total: int, took_ms: float) -> None:
    """Append one row to the query log, stamped with the current time.

    Raise SiftError if the database cannot be written.
    """
    row = QueryLogRow(
        at=datetime.now(UTC), query=query, total=total, took_ms=took_ms
    )
    try:
        with session_scope(path) as session:
            session.add(row)
    except SQLAlchemyError as error:
        raise SiftError(f"cannot log the query in {path}: {error}") from None


def recent_queries(path: Path, limit: int = 10) -> list[QueryLogRow]:
    """Return the last limit logged queries, newest first.

    A missing database holds no queries. Raise SiftError if the file
    cannot be read.
    """
    if not path.is_file():
        return []
    try:
        with session_scope(path) as session:
            stmt = select(QueryLogRow).order_by(QueryLogRow.id.desc())
            return list(session.scalars(stmt.limit(limit)))
    except SQLAlchemyError as error:
        raise SiftError(
            f"cannot read the query log in {path}: {error}"
        ) from None
