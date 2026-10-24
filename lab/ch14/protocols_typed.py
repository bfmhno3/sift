"""Structural typing: Protocol with a callable, attributes, generics."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sift.scoring import tf_idf


class Scorer(Protocol):
    """Anything callable like tf_idf: no inheritance needed."""

    def __call__(self, tf: int, df: int, n_docs: int) -> float:
        """Return the score of one term in one document."""
        ...


@runtime_checkable
class HasTitle(Protocol):
    """An object with a readable title attribute."""

    @property
    def title(self) -> str:
        """Return the title."""
        ...


class SupportsClose(Protocol):
    """An object that can be closed."""

    def close(self) -> None:
        """Release resources."""
        ...


@dataclass
class Post:
    """A post: it has a title, so it is a HasTitle."""

    title: str


class Handle:
    """A handle: it has close(), so it is a SupportsClose."""

    def __init__(self) -> None:
        """Start open."""
        self.closed = False

    def close(self) -> None:
        """Mark the handle as closed."""
        self.closed = True


def constant(tf: int, df: int, n_docs: int) -> float:
    """Return 1.0 whatever the counts: a Scorer too."""
    return 1.0


def best(scorer: Scorer, counts: Iterable[tuple[int, int]]) -> float:
    """Return the top score of (tf, df) pairs in a 100-document corpus."""
    return max(scorer(tf, df, 100) for tf, df in counts)


def close_all(things: Iterable[SupportsClose]) -> int:
    """Close every item and return how many there were."""
    count = 0
    for thing in things:
        thing.close()
        count += 1
    return count


def titles[T: HasTitle](items: Iterable[T]) -> list[str]:
    """Return the titles of items."""
    return [item.title for item in items]


def main() -> None:
    """Pass unrelated objects to functions typed with Protocols."""
    pairs = [(1, 10), (3, 2)]
    print(round(best(tf_idf, pairs), 3), best(constant, pairs))
    handles = [Handle(), Handle()]
    print(close_all(handles), all(h.closed for h in handles))
    print(titles([Post("a"), Post("b")]))
    things: list[object] = [Post("x"), Handle()]
    print([isinstance(thing, HasTitle) for thing in things])


if __name__ == "__main__":
    main()
