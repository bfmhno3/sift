"""Base types of the analysis package: Analyzer and TokenFilter."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import Any, Protocol

from sift.analysis.tokenize import Token

REGISTRY: dict[str, type[Analyzer]] = {}


class Analyzer(ABC):
    """Turn text into a stream of tokens.

    A concrete subclass names itself in the class statement,
    ``class Foo(Analyzer, name="foo")``, and lands in REGISTRY under
    that name.
    """

    name: str

    def __init_subclass__(cls, /, name: str, **kwargs: Any) -> None:
        """Register the subclass in REGISTRY under name."""
        super().__init_subclass__(**kwargs)
        if name in REGISTRY:
            raise ValueError(f"analyzer name taken: {name!r}")
        cls.name = name
        REGISTRY[name] = cls

    @abstractmethod
    def analyze(self, text: str) -> Iterator[Token]:
        """Yield the tokens of text."""


class TokenFilter(Protocol):
    """Anything callable that maps a token stream to a token stream."""

    def __call__(self, tokens: Iterable[Token]) -> Iterator[Token]:
        """Return the filtered tokens."""
        ...
