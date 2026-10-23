"""SQL injection: a formatted query leaks every row, a bound one not."""

import sqlite3

SECRET_ROWS = [
    ("alice", "public", "hello"),
    ("alice", "private", "alice's diary"),
    ("bob", "private", "bob's password is hunter2"),
]
HOSTILE = "x' OR 1=1 --"
STACKED = "x'; DROP TABLE notes; --"


def make_db() -> sqlite3.Connection:
    """Return an in-memory database with three notes."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE notes (owner TEXT, kind TEXT, body TEXT)")
    conn.executemany("INSERT INTO notes VALUES (?, ?, ?)", SECRET_ROWS)
    return conn


def formatted(conn: sqlite3.Connection, owner: str) -> list[tuple]:
    """Build the query with an f-string, the way not to."""
    sql = (
        f"SELECT body FROM notes WHERE owner = '{owner}' "  # BAD
        "AND kind = 'public'"
    )
    print("   sql:", sql)
    return conn.execute(sql).fetchall()


def bound(conn: sqlite3.Connection, owner: str) -> list[tuple]:
    """Good: the driver sends owner as a value, never as SQL."""
    sql = "SELECT body FROM notes WHERE owner = ? AND kind = 'public'"
    return conn.execute(sql, (owner,)).fetchall()


def main() -> None:
    """Run the same three inputs through both functions."""
    conn = make_db()
    for owner in ("alice", HOSTILE):
        print(f"input {owner!r}")
        print("   formatted ->", formatted(conn, owner))
        print("   bound     ->", bound(conn, owner))
    print()
    print("a comment cuts the rest of the query off")
    print("   formatted ->", formatted(conn, "bob' --"))
    print("   bound     ->", bound(conn, "bob' --"))
    print()
    # sqlite3.execute() runs one statement, so stacking fails here;
    # executescript() would run it (and drop the table)
    print(f"input {STACKED!r}")
    try:
        formatted(conn, STACKED)
    except sqlite3.ProgrammingError as error:
        print("   execute     ->", type(error).__name__, error)
    conn.executescript(
        f"SELECT 1 FROM notes WHERE owner = '{STACKED}' AND kind = 'x'"
    )
    print("   executescript ->", end=" ")
    try:
        conn.execute("SELECT count(*) FROM notes")
    except sqlite3.OperationalError as error:
        print(error)


if __name__ == "__main__":
    main()
