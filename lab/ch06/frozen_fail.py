"""Assigning to a field of a frozen dataclass raises."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Posting:
    """An immutable (doc_id, positions) pair."""

    doc_id: int
    positions: tuple[int, ...]


def main() -> None:
    """Try to change doc_id after construction."""
    p = Posting(1, (0, 3))
    print("before:", p)
    # error: dataclasses.FrozenInstanceError: cannot assign to field
    # 'doc_id'
    p.doc_id = 2


if __name__ == "__main__":
    main()
