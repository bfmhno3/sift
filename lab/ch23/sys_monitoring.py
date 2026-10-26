"""sys.monitoring (PEP 669): count calls without a profiler's cost.

The monitoring API reports events (``PY_START`` when a Python
function begins) to callbacks, and the interpreter pays only for
the events a tool asked for. Here a tool counts the Python calls
that analyzing one post makes; the same run under cProfile shows
the price of the deterministic profiler against the price of one
event.
"""

import cProfile
import sys
import timeit
from collections import Counter
from pathlib import Path
from types import CodeType

from sift.analysis import build_pipeline
from sift.corpus import iter_documents

TOOL = sys.monitoring.PROFILER_ID
REPEAT = 5


def main() -> None:
    """Count PY_START per function, then compare the overhead."""
    docs = list(iter_documents(Path("tests/fixtures/mini")))
    pipeline = build_pipeline(["mixed", "nfkc", "stopwords"])
    text = docs[0].body

    def analyze() -> int:
        return len(pipeline.terms(text))

    counts: Counter[str] = Counter()

    def on_start(code: CodeType, offset: int) -> None:
        counts[code.co_qualname] += 1

    monitoring = sys.monitoring
    monitoring.use_tool_id(TOOL, "sift-count")
    monitoring.register_callback(TOOL, monitoring.events.PY_START, on_start)
    monitoring.set_events(TOOL, monitoring.events.PY_START)
    terms = analyze()
    monitoring.set_events(TOOL, 0)
    print(f"{terms} terms; Python functions started, by name:")
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{count:>6}  {name}")

    plain = min(timeit.repeat(analyze, number=50, repeat=REPEAT))
    monitoring.set_events(TOOL, monitoring.events.PY_START)
    watched = min(timeit.repeat(analyze, number=50, repeat=REPEAT))
    monitoring.set_events(TOOL, 0)
    monitoring.register_callback(TOOL, monitoring.events.PY_START, None)
    monitoring.free_tool_id(TOOL)

    profiler = cProfile.Profile()
    profiler.enable()
    profiled = min(timeit.repeat(analyze, number=50, repeat=REPEAT))
    profiler.disable()
    print(f"no tool:       {plain / 50 * 1e6:8.1f} us per run")
    print(
        f"sys.monitoring {watched / 50 * 1e6:8.1f} us per run "
        f"({watched / plain:.2f}x)"
    )
    print(
        f"cProfile       {profiled / 50 * 1e6:8.1f} us per run "
        f"({profiled / plain:.2f}x)"
    )


if __name__ == "__main__":
    main()
