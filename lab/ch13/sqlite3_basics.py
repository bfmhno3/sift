"""sqlite3 in depth: DB-API 2.0, binding, rows, transactions."""

import sqlite3


def show_module() -> None:
    """Print the DB-API 2.0 module globals and the library versions."""
    print("apilevel     :", sqlite3.apilevel)
    print("paramstyle   :", sqlite3.paramstyle)
    print("threadsafety :", sqlite3.threadsafety)
    print("sqlite       :", sqlite3.sqlite_version)


def basics(conn: sqlite3.Connection) -> None:
    """Create a table, insert with executemany, fetch three ways."""
    cur = conn.cursor()
    cur.execute("CREATE TABLE post (id INTEGER PRIMARY KEY, title TEXT)")
    rows = [("kalman",), ("rust",), ("typst",), ("sqlite",)]
    cur.executemany("INSERT INTO post (title) VALUES (?)", rows)
    print("rowcount     :", cur.rowcount, " lastrowid:", cur.lastrowid)
    cur.execute("SELECT id, title FROM post ORDER BY id")
    print("fetchone     :", cur.fetchone())
    print("fetchmany(2) :", cur.fetchmany(2))
    print("fetchall     :", cur.fetchall())
    print("description  :", [c[0] for c in cur.description])
    # named parameters take a dict, qmark ones a sequence
    cur.execute("SELECT title FROM post WHERE id = :id", {"id": 2})
    print("named bind   :", cur.fetchone())
    # a placeholder is a value, never a table or column name
    try:
        cur.execute("SELECT title FROM ? WHERE id = 1", ("post",))
    except sqlite3.OperationalError as error:
        print("table as ?   :", type(error).__name__, error)
    # wrong number of bindings
    try:
        cur.execute("SELECT title FROM post WHERE id = ?", (1, 2))
    except sqlite3.ProgrammingError as error:
        print("2 for 1 ?    :", type(error).__name__, error)


def row_factory() -> None:
    """Show tuples against sqlite3.Row."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'x')")
    plain = conn.execute("SELECT a, b FROM t").fetchone()
    print("tuple        :", plain)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT a, b AS letter FROM t").fetchone()
    print("Row          :", tuple(row), row.keys(), row["letter"], row[0])
    print("dict(Row)    :", dict(row))
    conn.close()


def transactions() -> None:
    """Commit and roll back with ``with conn``, legacy mode."""
    conn = sqlite3.connect(":memory:")
    print("isolation    :", repr(conn.isolation_level))
    print("autocommit   :", conn.autocommit, "(LEGACY_TRANSACTION_CONTROL)")
    conn.execute("CREATE TABLE t (n INTEGER PRIMARY KEY)")
    with conn:  # commits when the block ends
        conn.execute("INSERT INTO t VALUES (1)")
    print("in_transaction after with:", conn.in_transaction)
    try:
        with conn:  # rolls back when the block raises
            conn.execute("INSERT INTO t VALUES (2)")
            print("in_transaction inside   :", conn.in_transaction)
            conn.execute("INSERT INTO t VALUES (1)")  # duplicate key
    except sqlite3.IntegrityError as error:
        print("rolled back  :", error)
    print("rows         :", conn.execute("SELECT n FROM t").fetchall())
    # ``with conn`` does not close the connection
    conn.execute("SELECT 1")
    conn.close()


def autocommit_attribute() -> None:
    """The 3.12 ``autocommit`` attribute: PEP 249 transactions."""
    conn = sqlite3.connect(":memory:", autocommit=False)
    print("autocommit=False -> in_transaction:", conn.in_transaction)
    conn.execute("CREATE TABLE t (n)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.rollback()
    # DDL is transactional in SQLite: the CREATE TABLE is undone too
    tables = conn.execute("SELECT name FROM sqlite_master").fetchall()
    print("tables after rollback:", tables)
    conn.close()
    conn = sqlite3.connect(":memory:", autocommit=True)
    conn.execute("CREATE TABLE t (n)")
    conn.execute("INSERT INTO t VALUES (1)")
    print("autocommit=True -> in_transaction:", conn.in_transaction)
    conn.execute("BEGIN")
    print("after BEGIN     -> in_transaction:", conn.in_transaction)
    conn.execute("ROLLBACK")
    conn.close()
    conn = sqlite3.connect(":memory:", isolation_level=None)
    print("isolation_level=None -> autocommit:", conn.autocommit)
    conn.close()


def main() -> None:
    """Run the sections."""
    show_module()
    print()
    conn = sqlite3.connect(":memory:")
    basics(conn)
    conn.close()
    print()
    row_factory()
    print()
    transactions()
    print()
    autocommit_attribute()


if __name__ == "__main__":
    main()
