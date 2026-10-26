"""Zipf's law: word frequency against rank, slope with polyfit."""

import numpy as np

from sift.analysis import build_pipeline
from sift.analytics.stats import term_counts, zipf_fit
from sift.cli import load_index
from sift.config import load_config


def main() -> None:
    """Fit log(frequency) = log(c) + s * log(rank) on the corpus."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    counts = term_counts(index)
    print(f"{len(counts)} terms, {counts.sum()} tokens")
    print(f"top 5 counts: {counts[:5].tolist()}")
    once = int((counts == 1).sum())
    print(f"seen once: {once} terms ({once / len(counts):.0%})")

    ranks = np.arange(1, len(counts) + 1)
    slope, intercept = np.polyfit(np.log(ranks), np.log(counts), 1)
    print(f"all ranks:  exponent {slope:.3f}")
    for limit in (100, 1000, 10_000):
        fit = zipf_fit(counts, limit)
        print(f"ranks 1-{limit}: exponent {fit.exponent:.3f}")
    fit = zipf_fit(counts)
    print(f"count(rank) ~ {fit.scale:.0f} * rank^{fit.exponent:.3f}")
    for rank in (1, 10, 100, 1000):
        real = int(counts[rank - 1])
        model = float(fit(np.array([float(rank)]))[0])
        print(f"rank {rank:>4}: real {real:>6}, model {model:9.1f}")


if __name__ == "__main__":
    main()
