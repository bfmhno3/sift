"""Class decorators: take a class, return a class."""

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

CALLS: dict[str, int] = {}
KNOWN: dict[str, type] = {}


def register[C: type](cls: C) -> C:
    """Remember the class by name and return it unchanged."""
    KNOWN[cls.__name__] = cls
    return cls


def auto_repr[C: type](cls: C) -> C:
    """Add a __repr__ built from the attributes in __init__."""
    names = list(cls.__init__.__code__.co_varnames[1:])

    def __repr__(self: Any) -> str:
        pairs = ", ".join(f"{n}={getattr(self, n)!r}" for n in names)
        return f"{cls.__name__}({pairs})"

    cls.__repr__ = __repr__  # type: ignore[method-assign]
    return cls


def count_calls(cls: type) -> type:
    """Wrap every public method so it counts its calls."""

    def wrap(name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            key = f"{cls.__name__}.{name}"
            CALLS[key] = CALLS.get(key, 0) + 1
            return func(*args, **kwargs)

        return inner

    for name, value in list(vars(cls).items()):
        if callable(value) and not name.startswith("_"):
            setattr(cls, name, wrap(name, value))
    return cls


@register
@auto_repr
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


@count_calls
class Counter:
    def __init__(self) -> None:
        self.n = 0

    def bump(self) -> int:
        self.n += 1
        return self.n


@dataclass(frozen=True, order=True)
class Version:
    """@dataclass is a class decorator that writes methods."""

    major: int
    minor: int


@functools.total_ordering
class Grade:
    """total_ordering fills in the other comparisons."""

    def __init__(self, points: int) -> None:
        self.points = points

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Grade) and self.points == other.points

    def __lt__(self, other: Grade) -> bool:
        return self.points < other.points


def main() -> None:
    """Apply each decorator and show what changed."""
    print("Point(1, 2)      :", Point(1, 2))
    print("KNOWN            :", sorted(KNOWN))
    counter = Counter()
    counter.bump()
    counter.bump()
    print("CALLS            :", CALLS)
    print("bump.__name__    :", Counter.bump.__name__)
    print("Version(1,2)<(1,3):", Version(1, 2) < Version(1, 3))
    print("Grade(1) <= (2)  :", Grade(1) <= Grade(2))
    print("Grade(3) >= (2)  :", Grade(3) >= Grade(2))


if __name__ == "__main__":
    main()
