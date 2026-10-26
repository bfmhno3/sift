"""float32 against float64: memory, precision and the ranking."""

import numpy as np

from sift.analysis import build_pipeline
from sift.analytics.vectors import tfidf_matrix
from sift.cli import load_index
from sift.config import load_config


def main() -> None:
    """Compare the TF-IDF matrix in both widths."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    small, vocab = tfidf_matrix(index)
    big = small.astype(np.float64)
    print(f"matrix {small.shape}: {len(vocab)} terms")
    print(f"float32 {small.nbytes / 2**20:.1f} MiB")
    print(f"float64 {big.nbytes / 2**20:.1f} MiB")

    eps32, eps64 = np.finfo(np.float32).eps, np.finfo(np.float64).eps
    print(f"eps float32 {eps32:.3e}, float64 {eps64:.3e}")
    print(
        f"0.1 + 0.2 in float32: {float(np.float32(0.1) + np.float32(0.2))!r}"
    )
    print(f"0.1 + 0.2 in float64: {0.1 + 0.2!r}")

    # the rows were scaled in float32, so redo the norm in float64
    big /= np.linalg.norm(big, axis=1, keepdims=True)
    sims32 = small @ small.T
    sims64 = big @ big.T
    gap = np.abs(sims32.astype(np.float64) - sims64).max()
    print(f"largest cosine difference: {gap:.2e}")

    differ = 0
    for row in range(len(small)):
        order32 = np.argsort(-sims32[row], kind="stable")[:10]
        order64 = np.argsort(-sims64[row], kind="stable")[:10]
        differ += int(not np.array_equal(order32, order64))
    print(f"documents whose top-10 differs: {differ} of {len(small)}")

    rng = np.random.default_rng(1234)
    noise = rng.random(10_000_000, dtype=np.float32)
    print(f"sum of 1e7 float32: {noise.sum(dtype=np.float32):.1f}")
    print(f"same, summed in float64: {noise.sum(dtype=np.float64):.1f}")


if __name__ == "__main__":
    main()
