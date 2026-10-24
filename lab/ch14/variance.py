"""Variance: why list[int] is not a list[float], and Sequence is.

With PEP 695 syntax the checker infers the variance of a type
parameter from how the class uses it.
"""

from collections.abc import Sequence


class Animal:
    """The base class of the example hierarchy."""

    def name(self) -> str:
        """Return a name."""
        return "animal"


class Dog(Animal):
    """A subtype of Animal."""

    def name(self) -> str:
        """Return a name."""
        return "dog"


class Box[T]:
    """Read only: T is only returned, so Box is covariant in T."""

    def __init__(self, item: T) -> None:
        """Keep item."""
        self._item = item

    def get(self) -> T:
        """Return the item."""
        return self._item


class Sink[T]:
    """Write only: T is only taken, so Sink is contravariant in T."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.seen: list[str] = []

    def put(self, item: T) -> None:
        """Record the repr of item."""
        self.seen.append(repr(item))


class Slot[T]:
    """Read and write: Slot is invariant in T."""

    def __init__(self, item: T) -> None:
        """Keep item."""
        self.item = item


def name_of(box: Box[Animal]) -> str:
    """Read the animal in a box."""
    return box.get().name()


def feed(sink: Sink[Dog]) -> None:
    """Give a dog to a sink."""
    sink.put(Dog())


def mean(values: Sequence[float]) -> float:
    """Return the mean; a Sequence is covariant, so list[int] fits."""
    return sum(values) / len(values)


def main() -> None:
    """Show the assignments that are allowed."""
    print(name_of(Box(Dog())))  # Box[Dog] is a Box[Animal]
    sink: Sink[Animal] = Sink()
    feed(sink)  # Sink[Animal] is a Sink[Dog]
    print(sink.seen[0].startswith("<"))
    ints = [1, 2, 3]
    print(mean(ints))  # list[int] is a Sequence[float]
    slot = Slot(Dog())
    slot.item = Dog()  # only Slot[Dog] accepts a Slot[Dog]
    print(slot.item.name())


if __name__ == "__main__":
    main()
