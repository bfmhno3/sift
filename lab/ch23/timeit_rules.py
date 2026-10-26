"""Rules for timing code: repeat, take the minimum, keep setup out.

One ``perf_counter`` pair around one run measures the machine as much
as the code. ``timeit.repeat`` runs the statement many times in a
row, with the garbage collector off, and the minimum of the repeats
is the run least disturbed by the rest of the system.
"""

import statistics
import time
import timeit
from pathlib import Path

from sift.analysis.tokenize import iter_tokens
from sift.config import load_config
from sift.corpus import iter_documents

NUMBER = 20
REPEAT = 7


def count_tokens(text: str) -> int:
    """Run the tokenizer to the end: a generator does nothing alone."""
    return sum(1 for _ in iter_tokens(text))


def main() -> None:
    """Time iter_tokens on one post the wrong way and the right way."""
    config = load_config()
    docs = iter_documents(Path(config.corpus))
    text = max((d.body for d in docs), key=len)
    print(f"text: {len(text)} characters, {count_tokens(text)} tokens")

    lazy = timeit.timeit(lambda: iter_tokens(text), number=NUMBER)
    full = timeit.timeit(lambda: count_tokens(text), number=NUMBER)
    print(f"rule 1, run the generator: {lazy / full:.4f} of the real cost")
    print("  (iter_tokens(text) alone builds a generator and stops)")

    singles = []
    for _ in range(REPEAT):
        start = time.perf_counter_ns()
        count_tokens(text)
        singles.append(time.perf_counter_ns() - start)
    print("rule 2, one run is one sample:")
    print(
        f"  {REPEAT} single runs: min {min(singles) / 1e6:.2f} ms, "
        f"max {max(singles) / 1e6:.2f} ms"
    )

    runs = timeit.repeat(
        lambda: count_tokens(text), number=NUMBER, repeat=REPEAT
    )
    per_call = [t / NUMBER * 1e3 for t in runs]
    print("rule 3, repeat, then take the minimum:")
    print(
        f"  best {min(per_call):.2f} ms, "
        f"median {statistics.median(per_call):.2f} ms "
        f"({NUMBER} calls x {REPEAT} repeats)"
    )

    timer = timeit.Timer(lambda: count_tokens(text))
    number, total = timer.autorange()
    print(
        f"rule 4, autorange picks the loop count: {number} calls "
        f"took {total * 1e3:.0f} ms"
    )

    setup_cost = timeit.timeit(lambda: text.lower(), number=NUMBER)
    print(
        "rule 5, keep setup out of the statement: lower() alone is "
        f"{setup_cost / full * 100:.1f}% of one tokenizer run"
    )


if __name__ == "__main__":
    main()
