"""A tour of Python's basic objects, the way the REPL shows them."""

import math


def show(label: str, value: object) -> None:
    """Print a label, the value and its type."""
    print(f"{label:<28}{value!r:<62}{type(value).__name__}")


def main() -> None:
    """Print type, identity and arithmetic facts."""
    a = int("256")
    b = int("256")
    c = int("257")
    d = int("257")
    print("256 is 256 (built at runtime):", a is b)
    print("257 is 257 (built at runtime):", c is d)
    print("257 == 257:", c == d)
    print("id(256) same:", id(a) == id(b), "| id(257) same:", id(c) == id(d))

    big = 2**200
    show("2**200", big)
    print("digits in 2**200:", len(str(big)))
    print("bit_length of 2**200:", big.bit_length())

    show("0.1 + 0.2", 0.1 + 0.2)
    print("0.1 + 0.2 == 0.3:", 0.1 + 0.2 == 0.3)
    print("math.isclose:", math.isclose(0.1 + 0.2, 0.3))

    print("divmod(17, 5):", divmod(17, 5))
    print("divmod(-17, 5):", divmod(-17, 5))
    print("-17 // 5:", -17 // 5, "| -17 % 5:", -17 % 5)
    print("17 // -5:", 17 // -5, "| 17 % -5:", 17 % -5)
    print("7 / 2:", 7 / 2, "| 7 // 2:", 7 // 2, "| 2 ** -1:", 2**-1)

    x = 5
    print("1 < x < 10:", 1 < x < 10)
    print("1 < x < 3:", 1 < x < 3)
    print("True + True:", True + True)
    print("bool is int subclass:", issubclass(bool, int))

    data = [3, 1, 4, 1, 5, 9, 2, 6]
    queue = data[:]
    while (n := len(queue)) > 5:
        queue.pop()
        print(f"walrus: len was {n}, now {len(queue)}")
    show("None", None)


if __name__ == "__main__":
    main()
