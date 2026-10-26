"""gil_release.py: Rust threads run while Python threads wait for none.

The same work, the tokens of the corpus, four ways. Python threads that
run iter_tokens take turns on the GIL, so more threads do not help.
Python threads that call sift._rs.tokenize_many(part, 1) hold the GIL
only to convert the arguments and the result: the scan runs in
py.detach(), so those threads overlap. Last, one Python thread asks
Rust for N threads of its own (std::thread::scope). A fixed work is
split into N parts; speedup is the time with 1 thread over the time
with N. The conversion of the result into Python lists is the part that
cannot overlap, so the curve bends before N reaches the core count.
A second workload, long Latin runs with few tokens, leaves little to
convert and much to scan: there the Rust threads scale much further.
"""

import os
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sift._rs as raw
from sift.analysis.tokenize import fold, iter_tokens

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "posts"
MINI = ROOT / "tests" / "fixtures" / "mini"
RUNS = 5
WORKERS = [1, 2, 4, 8]
# The mini corpus is tiny; repeat it so a run lasts long enough.
MIN_BYTES = 4_000_000
# Few tokens, much text: one 5000-character word per text line.
LONG_TEXTS = 64
LONG_WORD = "x" * 4999 + " "
LONG_REPEAT = 400


def py_part(part: list[str]) -> int:
    return sum(len(list(iter_tokens(text))) for text in part)


def rust_part(part: list[str]) -> int:
    return sum(map(len, raw.tokenize_many(part, 1)))


def split(texts: list[str], n: int) -> list[list[str]]:
    """Return n parts of about the same number of characters."""
    parts: list[list[str]] = [[] for _ in range(n)]
    sizes = [0] * n
    for text in sorted(texts, key=len, reverse=True):
        i = sizes.index(min(sizes))
        parts[i].append(text)
        sizes[i] += len(text)
    return parts


def median_ms(run: Callable[[], int]) -> tuple[float, int]:
    """Return the median wall time of run() in ms, and its result."""
    times = []
    result = 0
    for _ in range(RUNS):
        start = time.perf_counter()
        result = run()
        times.append(time.perf_counter() - start)
    return statistics.median(times) * 1000, result


def threaded(
    work: Callable[[list[str]], int], texts: list[str], n: int
) -> Callable[[], int]:
    parts = split(texts, n)

    def run() -> int:
        with ThreadPoolExecutor(max_workers=n) as pool:
            return sum(pool.map(work, parts))

    return run


def table(title: str, rows: list[tuple[int, float, int]]) -> None:
    print(f"== {title}")
    print(f"{'threads':>8} {'ms':>9} {'speedup':>8}  tokens")
    base = rows[0][1]
    for n, ms, tokens in rows:
        print(f"{n:8} {ms:9.1f} {base / ms:7.2f}x  {tokens}")
    print()


def compare(title: str, texts: list[str]) -> None:
    """Print the tables of one workload and check the token counts."""
    size = sum(len(t.encode()) for t in texts)
    print(f"##### {title}: {len(texts)} texts, {size} bytes")
    print()
    results: dict[str, list[tuple[int, float, int]]] = {}
    for name, work in [("python", py_part), ("rust", rust_part)]:
        rows = []
        for n in WORKERS:
            ms, tokens = median_ms(threaded(work, texts, n))
            rows.append((n, ms, tokens))
        results[name] = rows
    table("Python threads, iter_tokens (the GIL)", results["python"])
    table(
        "Python threads, tokenize_many(part, 1) (GIL released)",
        results["rust"],
    )

    rows = []
    for n in WORKERS:
        ms, tokens = median_ms(
            lambda n=n: sum(map(len, raw.tokenize_many(texts, n)))
        )
        rows.append((n, ms, tokens))
    table("one Python thread, tokenize_many(all, N) (Rust threads)", rows)

    counts = {t for rows in results.values() for _, _, t in rows}
    assert len(counts) == 1, f"token counts differ: {counts}"
    py, rs = results["python"], results["rust"]
    best_py = max(py[0][1] / ms for _, ms, _ in py)
    best_rs = max(rs[0][1] / ms for _, ms, _ in rs)
    print(
        f"best speedup: python threads {best_py:.2f}x, "
        f"rust under Python threads {best_rs:.2f}x"
    )
    print()


def main() -> None:
    root = CORPUS if CORPUS.is_dir() else MINI
    texts = [
        fold(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.md"))
    ]
    size = sum(len(t.encode()) for t in texts)
    texts *= max(1, MIN_BYTES // size)
    print(f"source: {root.relative_to(ROOT)}")
    print(f"cpus: {os.cpu_count()}, runs: {RUNS}, median")
    print()
    compare("corpus", texts)
    compare("long runs", [LONG_WORD * LONG_REPEAT] * LONG_TEXTS)


if __name__ == "__main__":
    main()
