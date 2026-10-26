"""tokenizer_bench.py: Python, ctypes, cffi, Cython and the C API.

Three measurements, each the median of several runs:

1. tokenize the whole corpus (NFKC and casefold included, they stay
   in Python): python, ctypes, cffi, Cython. The C API module only
   counts, so it is not in this table.
2. count the CJK characters of the whole corpus: all five.
3. the cost of one call on a 10-byte string: all five, for count_cjk,
   plus a Python function that does nothing as the floor.

The ratio is the time of the Python row divided by the row's time.
"""

import re
import statistics
import time
from collections.abc import Callable
from pathlib import Path

from sift.analysis.tokenize import CJK, fold, iter_tokens
from sift.ext import _capi, _cytok, cffitok, ctok

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "posts"
MINI = ROOT / "tests" / "fixtures" / "mini"
RUNS = 7
CALLS = 200_000
SHORT = "ab中cdefg"

_CJK_RUN = re.compile(f"[{CJK}]+")


def py_tokens(text: str) -> int:
    return len(list(iter_tokens(text)))


def c_tokens(text: str) -> int:
    return len(ctok.tokens(fold(text)))


def cffi_tokens(text: str) -> int:
    return len(cffitok.tokens(fold(text)))


def cy_tokens(text: str) -> int:
    return len(_cytok.tokens(fold(text)))


def py_count(text: str) -> int:
    return sum(map(len, _CJK_RUN.findall(text)))


def nothing(text: str) -> int:
    return 0


def median_ns(run: Callable[[], object], runs: int = RUNS) -> float:
    """Return the median wall time of run() in nanoseconds."""
    times = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        run()
        times.append(time.perf_counter_ns() - start)
    return statistics.median(times)


def over_texts(func: Callable[[str], int], texts: list[str]) -> int:
    return sum(func(text) for text in texts)


def table(
    title: str, rows: list[tuple[str, float, int]], unit: str, div: float
) -> None:
    """Print rows of (name, ns, result) with ratio to the first row."""
    print(f"== {title}")
    base = rows[0][1]
    print(f"{'':10} {unit:>12} {'ratio':>8}  result")
    for name, ns, result in rows:
        print(f"{name:10} {ns / div:12.1f} {base / ns:7.2f}x  {result}")
    print()


def bench_corpus(texts: list[str]) -> None:
    size = sum(len(t.encode()) for t in texts)
    print(f"corpus: {len(texts)} files, {size} bytes, {RUNS} runs, median")
    print()
    fold_ns = median_ns(lambda: [fold(t) for t in texts])
    token_funcs = [
        ("python", py_tokens),
        ("ctypes", c_tokens),
        ("cffi", cffi_tokens),
        ("cython", cy_tokens),
    ]
    rows = [
        (
            name,
            median_ns(lambda f=f: over_texts(f, texts)),
            over_texts(f, texts),
        )
        for name, f in token_funcs
    ]
    counts = {n for _, _, n in rows}
    assert len(counts) == 1, f"token counts differ: {rows}"
    table("tokenize the corpus (fold included)", rows, "ms", 1e6)
    print(f"fold alone (Python, in every row): {fold_ns / 1e6:.1f} ms")
    print()

    folded = [fold(t) for t in texts]
    count_funcs = [
        ("python", py_count),
        ("ctypes", ctok.count_cjk),
        ("cffi", cffitok.count_cjk),
        ("cython", _cytok.count_cjk),
        ("capi", _capi.count_cjk),
    ]
    rows = [
        (
            name,
            median_ns(lambda f=f: over_texts(f, folded)),
            over_texts(f, folded),
        )
        for name, f in count_funcs
    ]
    assert len({n for _, _, n in rows}) == 1, f"counts differ: {rows}"
    table("count CJK characters of the corpus", rows, "ms", 1e6)


def bench_calls() -> None:
    assert len(SHORT.encode()) == 10
    funcs = [
        ("python fn", nothing),
        ("python re", py_count),
        ("ctypes", ctok.count_cjk),
        ("cffi", cffitok.count_cjk),
        ("cython", _cytok.count_cjk),
        ("capi", _capi.count_cjk),
    ]
    rows = []
    for name, func in funcs:

        def loop(func: Callable[[str], int] = func) -> None:
            for _ in range(CALLS):
                func(SHORT)

        rows.append((name, median_ns(loop), func(SHORT)))
    print(f"10-byte string {SHORT!r}, {CALLS} calls per run")
    base = rows[0][1]
    print(f"{'':10} {'ns/call':>12} {'vs fn':>8}  result")
    for name, ns, result in rows:
        print(f"{name:10} {ns / CALLS:12.1f} {ns / base:7.2f}x  {result}")


def main() -> None:
    root = CORPUS if CORPUS.is_dir() else MINI
    texts = [p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))]
    print(f"source: {root.relative_to(ROOT)}")
    bench_corpus(texts)
    bench_calls()


if __name__ == "__main__":
    main()
