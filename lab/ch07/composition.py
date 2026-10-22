"""Pipeline by composition against a hierarchy of combinations."""

import re
from collections.abc import Iterator
from itertools import product

from sift.analysis import (
    FILTERS,
    REGISTRY,
    STOPWORDS,
    NfkcCasefold,
    StopwordFilter,
    Token,
    build_pipeline,
)

TEXT = "The Kalman Filter and the C++ port"


class LatinBase:
    """Hierarchy level 1: split into Latin words."""

    def analyze(self, text: str) -> Iterator[Token]:
        """Yield one token per Latin or digit run."""
        for i, m in enumerate(
            re.finditer(r"[0-9a-zA-Z_]+(?:\+{1,2}|#)?", text)
        ):
            yield Token(m[0], i, m.start(), m.end())


class LatinFolded(LatinBase):
    """Hierarchy level 2: tokenizer plus folding in one class."""

    def analyze(self, text: str) -> Iterator[Token]:
        """Fold token texts after the parent tokenizes."""
        for token in super().analyze(text):
            yield token._replace(text=token.text.casefold())


class LatinFoldedStop(LatinFolded):
    """Hierarchy level 3: one more behaviour, one more level."""

    def analyze(self, text: str) -> Iterator[Token]:
        """Drop stopwords after the parent folds."""
        for token in super().analyze(text):
            if token.text not in STOPWORDS:
                yield token


def texts(tokens: list[Token]) -> list[str]:
    """Return the token texts."""
    return [t.text for t in tokens]


def main() -> None:
    """Build the same analyzer both ways and count the classes."""
    by_hierarchy = texts(list(LatinFoldedStop().analyze(TEXT)))
    by_pipeline = build_pipeline(["latin", "nfkc", "stopwords"])
    print("hierarchy:", by_hierarchy)
    print("pipeline :", by_pipeline.terms(TEXT))
    print("same     :", by_hierarchy == by_pipeline.terms(TEXT))

    n_tok, n_filt = len(REGISTRY), len(FILTERS)
    # every subset of filters, in a fixed order, per tokenizer
    combos = n_tok * 2**n_filt
    print(f"{n_tok} tokenizers, {n_filt} filters")
    print(f"one class per combination: {combos} classes")
    print(f"composition: {n_tok + n_filt} classes + Pipeline")
    print("with 10 tokenizers and 10 filters:", 10 * 2**10, "vs", 20)

    print("every combination, built by composition:")
    for tok, flags in product(REGISTRY, product([0, 1], repeat=n_filt)):
        names = [tok, *(f for f, on in zip(FILTERS, flags, strict=True) if on)]
        print(f"  {' + '.join(names):32}", build_pipeline(names).terms(TEXT))
    print("filters used:", NfkcCasefold.name, StopwordFilter.name)


if __name__ == "__main__":
    main()
