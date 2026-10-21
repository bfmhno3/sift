"""Rich comparisons and functools.total_ordering."""

from functools import total_ordering


class Manual:
    """Defines only __lt__: the other operators are missing."""

    def __init__(self, n: int) -> None:
        """Store the number."""
        self.n = n

    def __lt__(self, other: Manual) -> bool:
        """Return True if self.n < other.n."""
        return self.n < other.n


@total_ordering
class Score:
    """Defines __eq__ and __lt__; total_ordering derives the rest."""

    def __init__(self, value: float) -> None:
        """Store the score."""
        self.value = value

    def __eq__(self, other: object) -> bool:
        """Compare scores for equality."""
        if not isinstance(other, Score):
            return NotImplemented
        return self.value == other.value

    def __lt__(self, other: object) -> bool:
        """Return True if self scores lower than other."""
        if not isinstance(other, Score):
            return NotImplemented
        return self.value < other.value

    def __repr__(self) -> str:
        """Return the constructor-style form."""
        return f"Score({self.value})"


def main() -> None:
    """Show sorting, derived operators and reflected comparison."""
    print("Manual < :", Manual(1) < Manual(2))
    print("Manual > works by reflection:", Manual(2) > Manual(1))
    try:
        print(Manual(1) <= Manual(2))
    except TypeError as exc:
        print("Manual <= ->", exc)

    a, b = Score(1.5), Score(2.5)
    print("<, <=, >, >=:", a < b, a <= b, a > b, a >= b)
    print("sorted:", sorted([b, a, Score(0.5)]))
    print("max:", max(a, b))
    print(
        "derived by total_ordering:",
        sorted(n for n in ("__le__", "__gt__", "__ge__") if n in vars(Score)),
    )
    print("compare with int:", a.__lt__(3))
    print("tuples compare field by field:", (1, "b") < (1, "c"))


if __name__ == "__main__":
    main()
