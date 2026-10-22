"""typing.Protocol: structural subtyping, and runtime_checkable."""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable


class Scorer(Protocol):
    """Static only: isinstance() refuses it."""

    def score(self, tf: int) -> float:
        """Return a score."""
        ...


@runtime_checkable
class Closable(Protocol):
    """runtime_checkable: isinstance() checks method names."""

    def close(self) -> None:
        """Release the resource."""
        ...


class Doubler:
    """Never mentions Scorer; has a matching score()."""

    def score(self, tf: int) -> float:
        """Return twice tf."""
        return 2.0 * tf


class File:
    """Has close()."""

    def close(self) -> None:
        """Do nothing."""


class WrongSignature:
    """Has close(), but with a signature a checker would reject."""

    def close(self, force: bool, timeout: float) -> str:
        """Need two arguments and return a str."""
        return f"{force} {timeout}"


class Disabled:
    """Sets close to None: the protocol treats it as not implemented."""

    close = None


def best(scorers: Iterable[Scorer], tf: int) -> float:
    """Return the highest score; a type checker verifies the shape."""
    return max(s.score(tf) for s in scorers)


def main() -> None:
    """Check structure at run time, and see its limits."""
    print("best:", best([Doubler(), Doubler()], 4))
    try:
        isinstance(Doubler(), Scorer)
    except TypeError as exc:
        print("TypeError:", exc)
    print("File is Closable:", isinstance(File(), Closable))
    print("Doubler is Closable:", isinstance(Doubler(), Closable))
    # runtime_checkable tests names, not signatures or types.
    print(
        "WrongSignature is Closable:", isinstance(WrongSignature(), Closable)
    )
    print("Disabled is Closable:", isinstance(Disabled(), Closable))
    print("issubclass(File, Closable):", issubclass(File, Closable))
    print("Closable.__mro__:", [c.__name__ for c in Closable.__mro__])
    # A Rust trait is implemented with `impl Trait for Type`; a Protocol
    # needs no declaration at all, a method of the right name suffices.


if __name__ == "__main__":
    main()
