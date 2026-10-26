"""Pure Python dot products against numpy for the TF-IDF cosine."""

import statistics
import time
from collections.abc import Callable

import numpy as np

from sift.analysis import build_pipeline
from sift.analytics.vectors import tfidf_matrix
from sift.cli import load_index
from sift.config import load_config

ROUNDS = 5
QUERY_ROW = 0


def median_ms(run: Callable[[], object], rounds: int = ROUNDS) -> float:
    """Return the median wall time of run() in milliseconds."""
    times = []
    for _ in range(rounds):
        start = time.perf_counter_ns()
        run()
        times.append(time.perf_counter_ns() - start)
    return statistics.median(times) / 1e6


def main() -> None:
    """Cosine of one document against all, in Python and in numpy."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    matrix, vocab = tfidf_matrix(index)
    rows = matrix.tolist()
    target = rows[QUERY_ROW]
    print(f"{len(rows)} documents x {len(vocab)} terms")

    def python_loop() -> list[float]:
        return [
            sum(a * b for a, b in zip(row, target, strict=True))
            for row in rows
        ]

    def numpy_matvec() -> np.ndarray:
        return matrix @ matrix[QUERY_ROW]

    slow = python_loop()
    fast = numpy_matvec()
    assert np.allclose(slow, fast, atol=1e-5)
    python_ms = median_ms(python_loop)
    numpy_ms = median_ms(numpy_matvec)
    print(f"pure Python: {python_ms:9.2f} ms (median of {ROUNDS})")
    print(f"numpy @:     {numpy_ms:9.2f} ms (median of {ROUNDS})")
    print(f"speedup: {python_ms / numpy_ms:.0f}x")


if __name__ == "__main__":
    main()
