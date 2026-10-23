"""EXPLAIN QUERY PLAN: SCAN against SEARCH, and what an index changes."""

import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from sift.cli import CORPUS
from sift.storage.db import QueryLogRow, open_db
from sift.storage.store import DB, update_index

PIPELINE = ("mixed", "nfkc", "stopwords")
N_LOG = 5000


def plan(conn: sqlite3.Connection, sql: str, *args: object) -> None:
    """Print the SQL and its query plan."""
    print(" ", " ".join(sql.split()))
    for _, _, _, detail in conn.execute("EXPLAIN QUERY PLAN " + sql, args):
        print("     ->", detail)


def fill_log(db: Path) -> None:
    """Add N_LOG rows of fake query history to the database."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    maker = open_db(db)
    with maker.begin() as session:
        session.add_all(
            QueryLogRow(
                at=start + timedelta(minutes=n),
                query=f"query {n % 40}",
                total=n % 17,
                took_ms=1.0 + n % 9,
            )
            for n in range(N_LOG)
        )
    maker.kw["bind"].dispose()


def main() -> None:
    """Index the corpus in a temp dir and explain a few queries."""
    print("sqlite", sqlite3.sqlite_version)
    with tempfile.TemporaryDirectory(prefix="sift-plan-") as tmp:
        update_index(CORPUS, Path(tmp), PIPELINE)
        db = Path(tmp) / DB
        fill_log(db)
        conn = sqlite3.connect(db)

        print("\nby primary key")
        plan(conn, "SELECT title FROM documents WHERE doc_id = ?", 7)

        print("\nby category, no index")
        plan(conn, "SELECT doc_id FROM documents WHERE category = ?", "Note")
        conn.execute(
            "CREATE INDEX ix_documents_category ON documents (category)"
        )
        print("\nby category, after CREATE INDEX")
        plan(conn, "SELECT doc_id FROM documents WHERE category = ?", "Note")

        print("\nLIKE with a leading % cannot use an index")
        plan(conn, "SELECT doc_id FROM documents WHERE title LIKE ?", "%GDB%")

        print("\nsift stats: the last 10 queries (id is the rowid)")
        plan(conn, "SELECT * FROM query_log ORDER BY id DESC LIMIT 10")

        print("\nthe same by time, no index on at")
        plan(conn, "SELECT * FROM query_log ORDER BY at DESC LIMIT 10")
        conn.execute("CREATE INDEX ix_query_log_at ON query_log (at)")
        print("\nthe same by time, after CREATE INDEX on at")
        plan(conn, "SELECT * FROM query_log ORDER BY at DESC LIMIT 10")

        print("\ncovering index: only indexed columns are read")
        plan(conn, "SELECT at FROM query_log WHERE at > ?", "2026-01-03")
        conn.close()

        print("\nthe same plan through SQLAlchemy")
        maker = open_db(db)
        with maker() as session:
            rows = session.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT total FROM query_log "
                    "WHERE query = :q"
                ),
                {"q": "query 3"},
            )
            for row in rows:
                print("     ->", row.detail)
        maker.kw["bind"].dispose()


if __name__ == "__main__":
    main()
