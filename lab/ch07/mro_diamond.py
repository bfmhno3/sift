"""C3 linearization of a diamond, and how super() walks it."""


class Base:
    """Root of the diamond."""

    def hello(self) -> list[str]:
        """Return the trail so far: just this class."""
        return ["Base"]


class Left(Base):
    """Left side: calls super() once."""

    def hello(self) -> list[str]:
        """Add Left to whatever super() returns."""
        return ["Left", *super().hello()]


class Right(Base):
    """Right side: calls super() once."""

    def hello(self) -> list[str]:
        """Add Right to whatever super() returns."""
        return ["Right", *super().hello()]


class Bottom(Left, Right):
    """Bottom of the diamond: Left first, then Right."""

    def hello(self) -> list[str]:
        """Add Bottom to whatever super() returns."""
        return ["Bottom", *super().hello()]


class Flipped(Right, Left):
    """The same bases in the other order."""


def names(cls: type) -> list[str]:
    """Return the names in cls.__mro__."""
    return [c.__name__ for c in cls.__mro__]


def main() -> None:
    """Print the MROs and the call trails."""
    print("Bottom.__mro__ ", names(Bottom))
    print("Flipped.__mro__", names(Flipped))
    print("Left.__mro__   ", names(Left))
    # Left.hello calls super(): in a Bottom it reaches Right, not Base.
    print("Bottom().hello()", Bottom().hello())
    print("Flipped().hello()", Flipped().hello())
    # A plain Left has no Right behind it: super() reaches Base.
    print("Left().hello()  ", Left().hello())
    print("Base comes just before object:", names(Bottom)[-2] == "Base")


if __name__ == "__main__":
    main()
