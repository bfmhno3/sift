"""EAFP vs LBYL: the cost of try/except against an `in` check."""

import statistics
import timeit
from pathlib import Path

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.index import InvertedIndex

MINI = Path("tests/fixtures/mini")
N = 1_000_000
REPEAT = 7


def per_call_ns(stmt: str, setup: str, number: int = N) -> float:
    """Return the median ns per execution of stmt."""
    runs = timeit.repeat(stmt, setup, repeat=REPEAT, number=number)
    return statistics.median(runs) / number * 1e9


def main() -> None:
    """Time try, `in`, get and suppress on a hit and on a miss."""
    setup = "d = {str(i): i for i in range(1000)}; hit = '500'; miss = 'x'"
    variants = {
        "EAFP try/except KeyError": (
            "try:\n    d[{k}]\nexcept KeyError:\n    pass"
        ),
        "LBYL if k in d": "if {k} in d:\n    d[{k}]",
        "dict.get": "d.get({k})",
    }
    print(f"plain dict, median of {REPEAT} runs of {N:,} calls")
    results: dict[tuple[str, str], float] = {}
    for name, template in variants.items():
        for case in ("hit", "miss"):
            ns = per_call_ns(template.format(k=case), setup)
            results[name, case] = ns
            print(f"  {name:26} {case:5} {ns:7.1f} ns")
    for case in ("hit", "miss"):
        ratio = (
            results["EAFP try/except KeyError", case]
            / results["LBYL if k in d", case]
        )
        print(f"  try / in on a {case}: {ratio:.2f}x")

    pipeline = build_pipeline()
    index = InvertedIndex()
    for doc in iter_documents(MINI):
        index.add(doc, pipeline.analyze(doc.body))
    term = next(iter(index))
    print(f"\nInvertedIndex ({len(index)} terms), same two idioms")
    namespace = {"index": index, "hit": term, "miss": "no-such-term"}
    for case in ("hit", "miss"):
        eafp = timeit.repeat(
            f"try:\n    index[{case}]\nexcept KeyError:\n    pass",
            globals=namespace,
            repeat=REPEAT,
            number=100_000,
        )
        lbyl = timeit.repeat(
            f"if {case} in index:\n    index[{case}]",
            globals=namespace,
            repeat=REPEAT,
            number=100_000,
        )
        eafp_ns = statistics.median(eafp) / 100_000 * 1e9
        lbyl_ns = statistics.median(lbyl) / 100_000 * 1e9
        print(
            f"  {case:5} try {eafp_ns:7.1f} ns   in {lbyl_ns:7.1f} ns"
            f"   ratio {eafp_ns / lbyl_ns:.2f}x"
        )


if __name__ == "__main__":
    main()
