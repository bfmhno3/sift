"""final_bench.py: every tokenizer of the series on the same corpus.

Rows, each the median of several runs over the whole corpus:

  python ch22   iter_tokens as tag ch22 had it (git show ch22:...)
  python ch23   iter_tokens of this tree
  ctypes, cffi, cython   fold in Python, the scan in C
  rust          fold in Python, sift._rs.tokenize per text
  rust parallel fold in Python, one tokenize_many for all texts

NFKC and casefold run in Python in every row, so every row includes the
same fold time (printed on its own too). The ratio is the time of the
python ch22 row divided by the time of the row. The C API module only
counts CJK characters and cannot tokenize, so it has a second table
next to a regex, the way ch24 measured it. All token streams are
compared first: a fast wrong answer is not a row.
"""

import re
import statistics
import subprocess
import sys
import time
import types
from collections.abc import Callable
from pathlib import Path

from sift.analysis.tokenize import CJK, Token, fold, iter_tokens
from sift.ext import _capi, _cytok, cffitok, ctok, rs

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "posts"
MINI = ROOT / "tests" / "fixtures" / "mini"
RUNS = 7

_CJK_RUN = re.compile(f"[{CJK}]+")


def load_ch22() -> Callable[[str], list[Token]] | None:
    """Return iter_tokens of tag ch22 as a list function, or None."""
    shown = subprocess.run(
        ["git", "show", "ch22:src/sift/analysis/tokenize.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if shown.returncode != 0:
        return None
    module = types.ModuleType("tokenize_ch22")
    sys.modules[module.__name__] = module
    exec(compile(shown.stdout, "ch22/tokenize.py", "exec"), module.__dict__)

    def tokens(text: str) -> list[Token]:
        return [Token(*t) for t in module.iter_tokens(text)]

    return tokens


def median_ms(run: Callable[[], object]) -> float:
    """Return the median wall time of run() in milliseconds."""
    times = []
    for _ in range(RUNS):
        start = time.perf_counter_ns()
        run()
        times.append(time.perf_counter_ns() - start)
    return statistics.median(times) / 1e6


def main() -> None:
    root = CORPUS if CORPUS.is_dir() else MINI
    texts = [p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))]
    size = sum(len(t.encode()) for t in texts)
    print(
        f"source: {root.relative_to(ROOT)}, {len(texts)} files, {size} bytes"
    )
    print(f"{RUNS} runs, median; every row folds in Python")
    print()

    def native(module: types.ModuleType) -> Callable[[], list[list[Token]]]:
        return lambda: [module.tokens(fold(t)) for t in texts]

    rows: list[tuple[str, Callable[[], list[list[Token]]]]] = [
        ("python ch23", lambda: [list(iter_tokens(t)) for t in texts]),
        ("ctypes", native(ctok)),
        ("cffi", native(cffitok)),
        ("cython", native(_cytok)),
        ("rust", native(rs)),
        ("rust parallel", lambda: rs.tokens_many([fold(t) for t in texts])),
    ]
    old = load_ch22()
    if old is not None:
        rows.insert(0, ("python ch22", lambda: [old(t) for t in texts]))
    else:
        print("tag ch22 not found: python ch22 skipped, ratios use ch23")
    expected = [list(iter_tokens(t)) for t in texts]
    for name, run in rows:
        assert run() == expected, f"{name}: tokens differ from Python"
    print(f"token streams equal: {sum(map(len, expected))} tokens")
    print()

    results = [(name, median_ms(run)) for name, run in rows]
    base = results[0][1]
    print("== tokenize the corpus (fold included)")
    print(f"{'':14} {'ms':>9} {'ratio':>8}")
    for name, ms in results:
        print(f"{name:14} {ms:9.1f} {base / ms:7.2f}x")
    print()
    fold_ms = median_ms(lambda: [fold(t) for t in texts])
    print(f"fold alone (Python, inside every row): {fold_ms:.1f} ms")
    folded = [fold(t) for t in texts]
    print(
        "without fold:  "
        f"rust {median_ms(lambda: [rs.tokens(t) for t in folded]):.1f} ms, "
        "rust parallel "
        f"{median_ms(lambda: rs.tokens_many(folded)):.1f} ms, "
        "rust raw tuples "
        f"{median_ms(lambda: rs._rs.tokenize_many(folded)):.1f} ms"
    )
    print()

    counters: list[tuple[str, Callable[[str], int]]] = [
        ("regex", lambda t: sum(map(len, _CJK_RUN.findall(t)))),
        ("ctypes", ctok.count_cjk),
        ("cffi", cffitok.count_cjk),
        ("cython", _cytok.count_cjk),
        ("capi", _capi.count_cjk),
    ]
    totals = {name: sum(map(f, folded)) for name, f in counters}
    assert len(set(totals.values())) == 1, f"counts differ: {totals}"
    timed = [
        (name, median_ms(lambda f=f: sum(map(f, folded))))
        for name, f in counters
    ]
    print("== count the CJK characters (capi cannot tokenize)")
    print(f"{'':14} {'ms':>9} {'ratio':>8}")
    for name, ms in timed:
        print(f"{name:14} {ms:9.1f} {timed[0][1] / ms:7.2f}x")


if __name__ == "__main__":
    main()
