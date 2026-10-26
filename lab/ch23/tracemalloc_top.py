"""tracemalloc: which lines of Sift allocate the memory of an index.

tracemalloc records the traceback of every allocation, so a snapshot
can group the live memory by source line. It slows the program down
by a factor of a few; memray (``extra.sh``) does the same job from
outside the interpreter.
"""

import tracemalloc
from pathlib import Path

from sift.analysis import build_pipeline
from sift.cli import load_index
from sift.config import load_config

TOP = 10


def main() -> None:
    """Build the in-memory index and list its biggest allocators."""
    config = load_config()
    pipeline = build_pipeline(config.pipeline)
    tracemalloc.start()
    _, index = load_index(config.corpus, pipeline)
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    print(f"{len(index)} terms")
    print(f"live {current / 2**20:.1f} MiB, peak {peak / 2**20:.1f} MiB")
    root = Path.cwd()
    print(f"top {TOP} lines by live memory:")
    for stat in snapshot.statistics("lineno")[:TOP]:
        frame = stat.traceback[0]
        name = Path(frame.filename)
        if name.is_relative_to(root):
            name = name.relative_to(root)
        print(
            f"{stat.size / 2**20:7.2f} MiB {stat.count:>8} blocks  "
            f"{name.name}:{frame.lineno}"
        )


if __name__ == "__main__":
    main()
