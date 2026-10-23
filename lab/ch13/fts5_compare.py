"""Sift against SQLite FTS5 (unicode61 and trigram) on the 12 queries.

For each query of bench/queries.txt, translated to FTS5 syntax, print
the number of hits, the Jaccard overlap of the two top-10 doc id sets
(Sift against FTS5, ranked with ``bm25()``) and the latency of each
engine. Both engines return ten hits with a snippet. Everything is
built in a temporary directory.
"""

import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import sift.search
from sift.analysis import build_pipeline
from sift.cli import CORPUS, QUERIES
from sift.document import Document
from sift.search import Searcher
from sift.storage.store import open_index, update_index

PIPELINE = ("mixed", "nfkc", "stopwords")
ROUNDS = 15
TOP = 10
# Sift query -> (unicode61 MATCH string, trigram MATCH string). The
# trigram tokenizer has no prefix queries and cannot match fewer than
# three characters, so ``owner*`` becomes the substring ``owner`` and
# the two-character CJK words match nothing.
TRANSLATED = {
    "rust 所有权": ("rust 所有权", "rust 所有权"),
    "kalman filter": ("kalman filter", "kalman filter"),
    '"device tree"': ('"device tree"', '"device tree"'),
    "pid AND 积分": ("pid AND 积分", "pid AND 积分"),
    "tag:Rust lifetime": ("tags:rust lifetime", "tags:rust lifetime"),
    "矩阵 OR matrix": ("矩阵 OR matrix", "矩阵 OR matrix"),
    "typst -latex": ("typst NOT latex", "typst NOT latex"),
    "cmake vcpkg": ("cmake vcpkg", "cmake vcpkg"),
    "gdb 断点": ("gdb 断点", "gdb 断点"),
    "linux kernel module": ("linux kernel module", "linux kernel module"),
    "奇异值": ("奇异值", "奇异值"),
    "owner*": ("owner*", "owner"),
}


def build_fts(
    conn: sqlite3.Connection,
    name: str,
    tokenizer: str,
    docs: list[Document],
) -> bool:
    """Create and fill an FTS5 table; return False if SQLite lacks it."""
    try:
        conn.execute(
            f"CREATE VIRTUAL TABLE {name} USING fts5("
            f"title, body, tags, tokenize='{tokenizer}')"
        )
    except sqlite3.OperationalError as error:
        print(f"{name}: unavailable: {error}")
        return False
    conn.executemany(
        f"INSERT INTO {name} (rowid, title, body, tags) VALUES (?, ?, ?, ?)",
        [(d.doc_id, d.title, d.body, " ".join(d.tags)) for d in docs],
    )
    return True


def fts_top(conn: sqlite3.Connection, name: str, match: str) -> list[int]:
    """Return the doc ids of the top-10 hits, with a snippet each."""
    sql = (
        f"SELECT rowid, snippet({name}, 1, '[', ']', '…', 24) "
        f"FROM {name} WHERE {name} MATCH ? ORDER BY bm25({name}) LIMIT ?"
    )
    try:
        return [row[0] for row in conn.execute(sql, (match, TOP))]
    except sqlite3.OperationalError as error:
        print(f"  {name}: {match!r}: {error}")
        return []


def fts_total(conn: sqlite3.Connection, name: str, match: str) -> int:
    """Return how many documents match."""
    sql = f"SELECT count(*) FROM {name} WHERE {name} MATCH ?"
    try:
        return conn.execute(sql, (match,)).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


@contextmanager
def no_snippets() -> Iterator[None]:
    """Make Searcher skip the snippets, to time ranking alone."""
    original = sift.search.make_snippet
    sift.search.make_snippet = lambda text, terms: []
    try:
        yield
    finally:
        sift.search.make_snippet = original


def rank_only(searcher: Searcher, query: str) -> object:
    """Search without building the ten snippets."""
    with no_snippets():
        return searcher.search(query, TOP)


def jaccard(a: list[int], b: list[int]) -> float | None:
    """Return |A and B| / |A or B|, or None when both are empty."""
    union = set(a) | set(b)
    return len(set(a) & set(b)) / len(union) if union else None


def time_ms(call: Callable[[], object]) -> float:
    """Return the wall time of one call in milliseconds."""
    start = time.perf_counter_ns()
    call()
    return (time.perf_counter_ns() - start) / 1e6


def main() -> None:
    """Build the three engines and compare them query by query."""
    print("sqlite", sqlite3.sqlite_version)
    queries = [q for q in QUERIES.read_text("utf-8").splitlines() if q]
    with tempfile.TemporaryDirectory(prefix="sift-fts5-") as tmp:
        root = Path(tmp)
        update_index(CORPUS, root / "idx", PIPELINE)
        conn = sqlite3.connect(root / "fts.db")
        with open_index(root / "idx") as index:
            docs = sorted(index.documents.values(), key=lambda d: d.doc_id)
            engines = {
                name: tok
                for name, tok in (
                    ("unicode61", "unicode61"),
                    ("trigram", "trigram"),
                )
                if build_fts(conn, name, tok, docs)
            }
            conn.commit()
            searcher = Searcher(index, pipeline=build_pipeline(PIPELINE))
            sift_size = sum(
                (root / "idx" / f).stat().st_size
                for f in ("segment.sft", "sift.db")
            )
            fts_size = (root / "fts.db").stat().st_size
            print(f"{len(docs)} documents; {len(queries)} queries")
            print(f"sift segment + sift.db: {sift_size:,} bytes")
            print(f"fts.db with {sorted(engines)}: {fts_size:,} bytes")
            print(f"latency: median and min of {ROUNDS} rounds, in ms")
            report(conn, searcher, engines, queries)
        conn.close()


def report(
    conn: sqlite3.Connection,
    searcher: Searcher,
    engines: dict[str, str],
    queries: list[str],
) -> None:
    """Print one block per query, then the averages."""
    overlaps: dict[str, list[float]] = {name: [] for name in engines}
    ratios: dict[str, list[float]] = {name: [] for name in engines}
    rank_ratios: dict[str, list[float]] = {name: [] for name in engines}
    for query in queries:
        matches = dict(
            zip(("unicode61", "trigram"), TRANSLATED[query], strict=True)
        )
        result = searcher.search(query, TOP)
        sift_ids = [hit.doc_id for hit in result.hits]
        calls: dict[str, Callable[[], object]] = {
            "sift": lambda q=query: searcher.search(q, TOP),
            "sift-rank": lambda q=query: rank_only(searcher, q),
        }
        for name in engines:
            calls[name] = lambda n=name, m=matches[name]: fts_top(conn, n, m)
        times: dict[str, list[float]] = {name: [] for name in calls}
        for call in calls.values():
            call()  # warm up: caches, prepared statements
        for _ in range(ROUNDS):  # alternate the engines in every round
            for name, call in calls.items():
                times[name].append(time_ms(call))
        print()
        print(f"query {query!r}")
        print(
            f"  {'engine':<10}{'hits':>5}{'jaccard':>9}{'median':>9}{'min':>9}"
        )
        print(line("sift", result.total, None, times["sift"]))
        print(line("sift-rank", result.total, None, times["sift-rank"]))
        for name in engines:
            ids = fts_top(conn, name, matches[name])
            total = fts_total(conn, name, matches[name])
            score = jaccard(sift_ids, ids)
            print(line(name, total, score, times[name]))
            if score is not None:
                overlaps[name].append(score)
            fts = statistics.median(times[name])
            ratios[name].append(fts / statistics.median(times["sift"]))
            rank_ratios[name].append(
                fts / statistics.median(times["sift-rank"])
            )
    print()
    print("sift-rank: the same search with make_snippet stubbed out")
    for name in engines:
        mean = statistics.fmean(overlaps[name]) if overlaps[name] else 0.0
        print(
            f"{name}: mean Jaccard {mean:.3f} over {len(overlaps[name])} "
            f"queries, median latency ratio fts/sift "
            f"{statistics.median(ratios[name]):.3f}, fts/sift-rank "
            f"{statistics.median(rank_ratios[name]):.3f}"
        )


def line(
    name: str, total: int, score: float | None, times: list[float]
) -> str:
    """Format one engine's row."""
    shown = "-" if score is None else f"{score:.3f}"
    return (
        f"  {name:<10}{total:>5}{shown:>9}"
        f"{statistics.median(times):>9.3f}{min(times):>9.3f}"
    )


if __name__ == "__main__":
    main()
