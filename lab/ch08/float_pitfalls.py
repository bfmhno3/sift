"""Floats add up badly: sum, math.fsum, Decimal and Fraction."""

import math
import random
from decimal import Decimal
from fractions import Fraction


def main() -> None:
    """Show rounding, order dependence and exact alternatives."""
    print("0.1 + 0.2 =", 0.1 + 0.2, "==", 0.3, "?", 0.1 + 0.2 == 0.3)
    print("math.isclose(0.1 + 0.2, 0.3):", math.isclose(0.1 + 0.2, 0.3))
    tenth = [0.1] * 10
    print("sum([0.1] * 10) =", sum(tenth))
    print("fsum([0.1] * 10) =", math.fsum(tenth))
    big = [1e16, 1.0, -1e16]
    print("sum([1e16, 1, -1e16]) =", sum(big), "(1.0 was absorbed)")
    print("fsum([1e16, 1, -1e16]) =", math.fsum(big))
    rng = random.Random(1234)
    scores = [rng.random() * 10 for _ in range(100_000)]
    forward = sum(scores)
    backward = sum(reversed(scores))
    exact = math.fsum(scores)
    print("100000 scores summed in two orders:")
    print(f"  forward  {forward!r}")
    print(f"  backward {backward!r}")
    print(f"  fsum     {exact!r}")
    print("  forward == backward:", forward == backward)
    print("Decimal('0.1') * 3 =", Decimal("0.1") * 3)
    print("Decimal(0.1) =", Decimal(0.1))
    print("Fraction(1, 10) * 3 =", Fraction(1, 10) * 3)
    print("Fraction(0.1) =", Fraction(0.1))
    print("float.as_integer_ratio(0.1) =", (0.1).as_integer_ratio())
    print("math.log(1 + 1e-18) =", math.log(1 + 1e-18))
    print("math.log1p(1e-18) =", math.log1p(1e-18))


if __name__ == "__main__":
    main()
