"""Heaps' law: the vocabulary grows like K * n ** beta."""

import numpy as np

from sift.analysis import build_pipeline
from sift.analytics.stats import heaps_fit, vocabulary_growth
from sift.cli import load_index
from sift.config import load_config


def main() -> None:
    """Count the distinct terms after each document and fit the curve."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    tokens, vocabulary = vocabulary_growth(index)
    print(f"{tokens[-1]} tokens, {vocabulary[-1]} distinct terms")
    fit = heaps_fit(tokens, vocabulary)
    print(f"V(n) = {fit.scale:.2f} * n^{fit.exponent:.3f}")
    for i in (0, 9, 29, 59, len(tokens) - 1):
        n = float(tokens[i])
        model = float(fit(np.array([n]))[0])
        print(
            f"after {i + 1:>3} docs: n {int(n):>6}, "
            f"V {int(vocabulary[i]):>6}, model {model:9.0f}"
        )


if __name__ == "__main__":
    main()
