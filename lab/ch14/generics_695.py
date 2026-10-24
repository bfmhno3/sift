"""Generics: class and function syntax of 3.12+, bounds, constraints.

The same Stack is written twice, with PEP 695 syntax and with the
older TypeVar, then bounds, constraints, a TypeVarTuple and ``type``
aliases.
"""

from collections.abc import Callable, Hashable, Iterable
from typing import Generic, TypeVar

T_old = TypeVar("T_old")


class OldStack(Generic[T_old]):  # noqa: UP046  (old style on purpose)
    """A stack in the pre-3.12 style: TypeVar plus Generic."""

    def __init__(self) -> None:
        """Create an empty stack."""
        self._items: list[T_old] = []

    def push(self, item: T_old) -> None:
        """Put item on top."""
        self._items.append(item)

    def pop(self) -> T_old:
        """Remove and return the top item."""
        return self._items.pop()


class Stack[T]:
    """The same stack with PEP 695 syntax: no TypeVar, no Generic."""

    def __init__(self) -> None:
        """Create an empty stack."""
        self._items: list[T] = []

    def push(self, item: T) -> None:
        """Put item on top."""
        self._items.append(item)

    def pop(self) -> T:
        """Remove and return the top item."""
        return self._items.pop()

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._items)


def first[T](items: Iterable[T], default: T) -> T:
    """Return the first item, or default for an empty iterable."""
    for item in items:
        return item
    return default


def group_by[K: Hashable, V](
    items: Iterable[V], key: Callable[[V], K]
) -> dict[K, list[V]]:
    """Group items by key(item); K is bound to hashable types."""
    groups: dict[K, list[V]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return groups


def shout[S: (str, bytes)](value: S) -> S:
    """Upper-case a str or a bytes; S is one of the two, never a mix."""
    return value.upper()


def pairwise_sum[*Ts](left: tuple[*Ts], right: tuple[*Ts]) -> int:
    """Count the items of two tuples that have the same shape."""
    return len(left) + len(right)


type Pair[A, B] = tuple[A, B]
type ScoreTable = dict[int, float]
type Json = None | bool | int | float | str | list[Json] | dict[str, Json]


def swap[A, B](pair: Pair[A, B]) -> Pair[B, A]:
    """Return the pair with its items swapped."""
    return pair[1], pair[0]


def main() -> None:
    """Use every generic above and print the results."""
    old = OldStack[int]()
    old.push(1)
    new = Stack[str]()
    new.push("sift")
    print(old.pop(), new.pop(), len(new))
    print(first([3, 4], 0), first([], "empty"))
    print(group_by(["tea", "tar", "bike"], key=lambda w: w[0]))
    print(shout("sift"), shout(b"sift"))
    print(pairwise_sum((1, "a"), (2, "b")))
    table: ScoreTable = {1: 0.5}
    doc: Json = {"scores": [1, 2.5, None], "ok": True}
    print(swap((1, "x")), table, doc)
    print(Pair.__value__, Stack.__type_params__)


if __name__ == "__main__":
    main()
