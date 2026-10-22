"""Pipeline: one tokenizer followed by token filters."""

from collections.abc import Iterator, Sequence

from sift.analysis.base import REGISTRY, Analyzer, TokenFilter
from sift.analysis.filters import FILTERS
from sift.analysis.tokenize import Token
from sift.errors import ConfigError

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

    Raise ConfigError for an empty list, an unknown name, a filter
    name in the first place or a tokenizer name after it.
    """
    if not names:
        raise ConfigError("a pipeline needs a tokenizer, got no names")
    first, *rest = names
    if first not in REGISTRY:
        known = ", ".join(sorted(REGISTRY))
        raise ConfigError(f"unknown tokenizer {first!r}; known: {known}")
    for name in rest:
        if name not in FILTERS:
            known = ", ".join(sorted(FILTERS))
            raise ConfigError(f"unknown filter {name!r}; known: {known}")
    return Pipeline(REGISTRY[first](), *(FILTERS[name]() for name in rest))
