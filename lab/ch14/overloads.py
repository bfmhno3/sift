"""@overload: one function, several signatures, one implementation."""

from collections.abc import Sequence
from typing import overload, reveal_type

from sift.scoring import top_k


@overload
def parse_flag(value: str) -> bool: ...
@overload
def parse_flag(value: str, default: bool) -> bool: ...
@overload
def parse_flag(value: None, default: bool) -> bool: ...
def parse_flag(value: str | None, default: bool = False) -> bool:
    """Read "true"/"false"; None falls back to default."""
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes"}


@overload
def first_or[T](items: Sequence[T], default: None = None) -> T | None: ...
@overload
def first_or[T, D](items: Sequence[T], default: D) -> T | D: ...
def first_or(items: Sequence[object], default: object = None) -> object:
    """Return the first item, or default when the sequence is empty."""
    return items[0] if items else default


@overload
def best_scores(
    raw: dict[int, float], k: None = None
) -> tuple[int, float]: ...
@overload
def best_scores(raw: dict[int, float], k: int) -> list[tuple[int, float]]: ...
def best_scores(
    raw: dict[int, float], k: int | None = None
) -> tuple[int, float] | list[tuple[int, float]]:
    """Return the best entry without k, else the best k entries."""
    best = top_k(raw, 1 if k is None else k)
    return best[0] if k is None else best


def main() -> None:
    """Call every overload; the checker picks the return type."""
    print(parse_flag("TRUE"), parse_flag(None, True))
    print(first_or([1, 2]), first_or([], 5), first_or([]))
    table = {1: 0.5, 2: 1.5, 3: 1.0}
    print(best_scores(table), best_scores(table, 2))
    reveal_type(first_or([1, 2]))
    reveal_type(first_or([1, 2], "none"))
    reveal_type(best_scores(table))
    reveal_type(best_scores(table, 2))


if __name__ == "__main__":
    main()
