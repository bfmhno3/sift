"""The format mini-language."""

import math


class Point:
    """A class that defines its own format spec."""

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __format__(self, spec: str) -> str:
        return f"({self.x:{spec}}, {self.y:{spec}})"

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"


def main() -> None:
    """Print values with several format specs."""
    x = math.pi
    print(f"[{x:>10.3f}] [{x:<10.3f}] [{x:^10.3f}] [{x:+.2e}]")
    print(f"[{42:08d}] [{42:#x}] [{42:#b}] [{1234567:,}] [{0.256:.1%}]")
    print(f"[{'所有权':*^9}] [{'ab':>5}] [{'abcdef':.3}]")
    print(f"{x=} {x=:.2f} {1 + 2=}")
    name = "tea\n"
    print(f"{name!r} {name!s:>6} {'é'!a}")
    width, prec = 12, 4
    print(f"[{x:{width}.{prec}f}]")
    print(f"{Point(1.5, 2.25):.1f}", f"{Point(1, 2)!r}")
    old = "{0} {1} {0}"  # str.format, kept for stored templates
    print(old.format("a", "b"), "%s is %d" % ("tea", 3))  # noqa: UP031
    print(format(255, "08b"), format(3.0, "g"), f"{1e-7:g}")


if __name__ == "__main__":
    main()
