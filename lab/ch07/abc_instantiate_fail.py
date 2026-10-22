"""Instantiating a class that leaves an abstract method open."""

from abc import ABC, abstractmethod


class Scorer(ABC):
    """Two abstract methods."""

    @abstractmethod
    def score(self, tf: int) -> float:
        """Return a score."""

    @abstractmethod
    def name(self) -> str:
        """Return the scorer name."""


class Half(Scorer):
    """Implements only score()."""

    def score(self, tf: int) -> float:
        """Return tf as a float."""
        return float(tf)


def main() -> None:
    """Try to build the incomplete subclass."""
    print("still abstract:", sorted(Half.__abstractmethods__))
    # error: TypeError: Can't instantiate abstract class Half without
    # an implementation for abstract method 'name'
    Half()


if __name__ == "__main__":
    main()
