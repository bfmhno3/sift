"""cProfile of a full index build, printed with pstats.

A deterministic profiler hooks every call and return, so it sees all
the calls and slows the program down. The table is sorted by
cumulative time (a function and everything it calls), the 15 first
lines; the second table is sorted by own time and shows where the
interpreter really spends it. The stats are also saved in
``out/ch23/index.pstats``.
"""

import cProfile
import pstats
import tempfile
from pathlib import Path

from sift.config import load_config
from sift.storage.store import update_index

OUT = Path("out/ch23/index.pstats")


def main() -> None:
    """Profile update_index(full=True) over the corpus."""
    config = load_config()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        profiler = cProfile.Profile()
        profiler.enable()
        report = update_index(
            config.corpus,
            Path(tmp) / "idx",
            config.pipeline,
            full=True,
        )
        profiler.disable()
    print(f"indexed {report.documents} documents, {report.terms} terms")
    profiler.dump_stats(OUT)
    stats = pstats.Stats(profiler).strip_dirs()
    print("== sorted by cumulative time, top 15")
    stats.sort_stats(pstats.SortKey.CUMULATIVE).print_stats(15)
    print("== sorted by own time, top 5")
    stats.sort_stats(pstats.SortKey.TIME).print_stats(5)


if __name__ == "__main__":
    main()
