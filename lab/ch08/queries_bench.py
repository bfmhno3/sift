"""Latency of bench/queries.txt: median of five runs per query."""

import statistics
import time
from pathlib import Path

from sift.analysis import build_pipeline
from sift.cli import CORPUS, QUERIES, load_index
from sift.search import Searcher

REPEATS = 5


def main() -> None:
    """Build the index once, then time every query."""
    pipeline = build_pipeline()
    _, index = load_index(CORPUS, pipeline)
    searcher = Searcher(index, pipeline=pipeline)
    queries = Path(QUERIES).read_text(encoding="utf-8").splitlines()
    medians = []
    for query in filter(None, queries):
        runs = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            result = searcher.search(query)
            runs.append((time.perf_counter() - start) * 1000)
        medians.append(statistics.median(runs))
        print(f"{medians[-1]:8.2f} ms  {result.total:>4} hits  {query}")
    print(f"{sum(medians):8.2f} ms  sum of medians, {len(medians)} queries")


if __name__ == "__main__":
    main()
