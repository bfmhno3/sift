"""The iterator protocol: __iter__, __next__ and the for loop."""

from typing import Self


class Countdown:
    """An iterator that counts down from start to 1."""

    def __init__(self, start: int) -> None:
        self.current = start

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration
        value = self.current
        self.current -= 1
        return value


def main() -> None:
    """Drive the iterator by hand, then by a desugared for loop."""
    numbers = [10, 20, 30]
    print("list is iterable:", hasattr(numbers, "__iter__"))
    print("list is an iterator:", hasattr(numbers, "__next__"))
    it = iter(numbers)
    print("iter(list):", type(it).__name__, it is iter(it))
    print("two iter() calls differ:", iter(numbers) is not iter(numbers))

    counter = Countdown(3)
    print("iter(c) is c:", iter(counter) is counter)
    print(next(counter), next(counter), next(counter))
    try:
        next(counter)
    except StopIteration:
        print("fourth next(): StopIteration")
    print("next with default:", next(counter, "done"))

    print("for loop:", [n for n in Countdown(3)])

    # for item in Countdown(3): body, written out by hand
    iterator = iter(Countdown(3))
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            break
        print("desugared:", item)

    # Without __iter__ an object with __getitem__ still works.
    class Squares:
        def __getitem__(self, i: int) -> int:
            if i >= 4:
                raise IndexError
            return i * i

    print("old protocol:", list(Squares()))


if __name__ == "__main__":
    main()
