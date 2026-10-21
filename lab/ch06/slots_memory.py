"""__slots__ vs __dict__: size of one Posting and of 100,000."""

import sys
import tracemalloc
from dataclasses import dataclass

N = 100_000


@dataclass(frozen=True)
class DictPosting:
    """Posting with the default per-instance __dict__."""

    doc_id: int
    positions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SlotPosting:
    """The same fields stored in slots."""

    doc_id: int
    positions: tuple[int, ...]


def traced(cls: type, touch_dict: bool = False) -> float:
    """Return KiB held by N instances sharing one positions tuple.

    The figure includes the list slot (8 bytes) and one int object per
    doc_id. With touch_dict, read ``__dict__`` of every instance,
    which makes Python build the real dict object.
    """
    positions = (1, 2, 3)
    tracemalloc.start()
    held = [cls(i, positions) for i in range(N)]
    if touch_dict:
        for obj in held:
            _ = obj.__dict__
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(held) == N
    return current / 1024


def main() -> None:
    """Print per-object and per-100,000 memory for both layouts."""
    d = DictPosting(1, (1, 2, 3))
    s = SlotPosting(1, (1, 2, 3))
    print("has __dict__:", hasattr(d, "__dict__"), hasattr(s, "__dict__"))
    # Since 3.13 the values of a plain instance live inline in the
    # object and the dict is built on demand, so getsizeof says little.
    print("getsizeof(DictPosting):", sys.getsizeof(d))
    print("getsizeof(SlotPosting):", sys.getsizeof(s))
    print("getsizeof(d.__dict__):", sys.getsizeof(d.__dict__))
    dict_kib = traced(DictPosting)
    slot_kib = traced(SlotPosting)
    wide_kib = traced(DictPosting, touch_dict=True)
    print(f"tracemalloc, {N} DictPosting:       {dict_kib:7.0f} KiB")
    print(f"tracemalloc, {N} DictPosting+dict:  {wide_kib:7.0f} KiB")
    print(f"tracemalloc, {N} SlotPosting:       {slot_kib:7.0f} KiB")
    for name, kib in [
        ("DictPosting", dict_kib),
        ("DictPosting+dict", wide_kib),
        ("SlotPosting", slot_kib),
    ]:
        print(f"per {name}: {kib * 1024 / N:.0f} bytes")
    print(f"ratio dict/slots: {dict_kib / slot_kib:.2f}")
    print(f"ratio dict+dict/slots: {wide_kib / slot_kib:.2f}")


if __name__ == "__main__":
    main()
