"""datetime and sqlite3: the default adapters and what replaces them."""

import sqlite3
import warnings
from datetime import UTC, datetime

WHEN = datetime(2026, 10, 23, 8, 30, tzinfo=UTC)


def default_adapter() -> None:
    """Bind a datetime with no adapter registered: 3.12 warns."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (at TEXT)")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        conn.execute("INSERT INTO t VALUES (?)", (WHEN,))
    for w in caught:
        print(f"{w.category.__name__}: {w.message}")
    print("stored       :", conn.execute("SELECT at FROM t").fetchone())
    conn.close()


def explicit() -> None:
    """Convert by hand: ISO 8601 text in, datetime out."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (at TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", (WHEN.isoformat(),))
    (text,) = conn.execute("SELECT at FROM t").fetchone()
    back = datetime.fromisoformat(text)
    print("by hand      :", text, "->", back == WHEN)
    conn.close()


def register_your_own() -> None:
    """register_adapter and register_converter, as the docs recipe."""
    sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
    sqlite3.register_converter(
        "timestamp", lambda raw: datetime.fromisoformat(raw.decode())
    )
    conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("CREATE TABLE t (at timestamp)")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        conn.execute("INSERT INTO t VALUES (?)", (WHEN,))
    print("warnings     :", len(caught))
    (value,) = conn.execute("SELECT at FROM t").fetchone()
    print("round trip   :", repr(value), value == WHEN)
    conn.close()


def main() -> None:
    """Run the three sections."""
    print("default adapter (deprecated since 3.12)")
    default_adapter()
    print()
    print("explicit conversion")
    explicit()
    print()
    print("your own adapter and converter")
    register_your_own()


if __name__ == "__main__":
    main()
