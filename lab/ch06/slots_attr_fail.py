"""A class with __slots__ rejects attributes it did not declare."""


class Point:
    """Two slots and nothing else."""

    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        """Fill both slots."""
        self.x = x
        self.y = y


def main() -> None:
    """Add a third attribute to a Point."""
    p = Point(1, 2)
    print("slots:", Point.__slots__, "has __dict__:", hasattr(p, "__dict__"))
    # error: AttributeError: 'Point' object has no attribute 'z' and no
    # __dict__ for setting new attributes
    p.z = 3


if __name__ == "__main__":
    main()
