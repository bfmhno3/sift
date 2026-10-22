"""ABCs: abstract methods, virtual subclasses, __subclasshook__."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class Scorer(ABC):
    """Anything that turns (tf, df, n_docs) into a score."""

    @abstractmethod
    def score(self, tf: int, df: int, n_docs: int) -> float:
        """Return the score of one term in one document."""

    def describe(self) -> str:
        """Describe the analyzer; subclasses inherit this method."""
        return f"{type(self).__name__}: {self.score(3, 10, 100):.3f}"


class RawTf(Scorer):
    """Score by term frequency alone."""

    def score(self, tf: int, df: int, n_docs: int) -> float:
        """Return tf as a float."""
        return float(tf)


class Closer(ABC):
    """Anything with a close() method, declared or not."""

    @abstractmethod
    def close(self) -> None:
        """Release the resource."""

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        """Say yes to every class that defines close()."""
        if cls is Closer and callable(getattr(subclass, "close", None)):
            return True
        return NotImplemented


class Handle:
    """Never mentions Closer, yet counts as one."""

    def close(self) -> None:
        """Do nothing."""


class Unrelated:
    """No close() at all."""


class Legacy:
    """Registered by hand with Closer.register."""


Closer.register(Legacy)


def main() -> None:
    """Show instantiation, isinstance hooks and the registry."""
    print(RawTf().describe())
    print("Scorer.__abstractmethods__:", set(Scorer.__abstractmethods__))
    print("RawTf.__abstractmethods__:", set(RawTf.__abstractmethods__))
    print("RawTf is a Scorer:", issubclass(RawTf, Scorer))
    print("Handle is a Closer:", isinstance(Handle(), Closer))
    print("Unrelated is a Closer:", isinstance(Unrelated(), Closer))
    print("Legacy is a Closer:", isinstance(Legacy(), Closer))
    print("Closer in Handle.__mro__:", Closer in Handle.__mro__)
    print("list is a Sequence:", issubclass(list, Sequence))


if __name__ == "__main__":
    main()
