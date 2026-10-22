"""Token filters: normalization and stopword removal."""

from collections.abc import Iterable, Iterator

from sift.analysis.tokenize import Token, fold

FILTERS: dict[str, type[TokenFilterBase]] = {}

# Placeholder list; ch11 moves it into stopwords.txt.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)


class TokenFilterBase:
    """Base of the named filters: registers itself in FILTERS."""

    name: str

    def __init_subclass__(cls, /, name: str) -> None:
        """Register the subclass in FILTERS under name."""
        super().__init_subclass__()
        if name in FILTERS:
            raise ValueError(f"filter name taken: {name!r}")
        cls.name = name
        FILTERS[name] = cls

    def __call__(self, tokens: Iterable[Token]) -> Iterator[Token]:
        """Return the filtered tokens."""
        raise NotImplementedError


class NfkcCasefold(TokenFilterBase, name="nfkc"):
    """NFKC-normalize and casefold the text of every token."""

    def __call__(self, tokens: Iterable[Token]) -> Iterator[Token]:
        """Yield each token with its text folded."""
        for token in tokens:
            text = fold(token.text)
            if text != token.text:
                token = token._replace(text=text)
            yield token


class StopwordFilter(TokenFilterBase, name="stopwords"):
    """Drop tokens whose text is a stopword.

    Positions of the other tokens are not renumbered, so a phrase
    match still sees the gap.
    """

    def __init__(self, words: frozenset[str] = STOPWORDS) -> None:
        """Keep the stopword set."""
        self.words = words

    def __call__(self, tokens: Iterable[Token]) -> Iterator[Token]:
        """Yield the tokens that are not stopwords."""
        for token in tokens:
            if token.text not in self.words:
                yield token
