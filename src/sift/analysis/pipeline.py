"""Pipeline: one tokenizer followed by token filters."""

from collections.abc import Iterator, Sequence

from sift.analysis.base import REGISTRY, Analyzer, TokenFilter
from sift.analysis.filters import FILTERS
from sift.analysis.tokenize import Token

DEFAULT_NAMES = ("mixed", "nfkc")


class Pipeline:
    """Run a tokenizer, then each filter on the stream in order."""

    def __init__(self, tokenizer: Analyzer, *filters: TokenFilter) -> None:
        """Keep the tokenizer and the filters."""
        self.tokenizer = tokenizer
        self.filters = filters

    def analyze(self, text: str) -> Iterator[Token]:
        """Yield the tokens of text after every stage."""
        tokens = self.tokenizer.analyze(text)
        for stage in self.filters:
            tokens = stage(tokens)
        return tokens

    def terms(self, text: str) -> list[str]:
        """Return the token texts of text."""
        return [token.text for token in self.analyze(text)]

    def __repr__(self) -> str:
        """Return a repr that names every stage."""
        stages = [self.tokenizer, *self.filters]
        return f"Pipeline({', '.join(type(s).__name__ for s in stages)})"


def build_pipeline(names: Sequence[str] = DEFAULT_NAMES) -> Pipeline:
    """Build a Pipeline from names: a tokenizer, then filters.

    Raise KeyError for an unknown name, or for a filter name in the
    first place or a tokenizer name after it.
    """
    first, *rest = names
    tokenizer = REGISTRY[first]()
    return Pipeline(tokenizer, *(FILTERS[name]() for name in rest))
