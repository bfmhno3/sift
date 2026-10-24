"""Reference counts, a cycle, gc.collect(), gc.callbacks."""

import gc
import sys
import weakref
from typing import Any


class Node:
    """A plain object that can point at another one."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.other: Node | None = None


events: list[str] = []


def watch(phase: str, info: dict[str, Any]) -> None:
    """gc.callbacks hook: record each collection."""
    if phase == "stop":
        events.append(
            f"gen {info['generation']}: collected {info['collected']},"
            f" uncollectable {info['uncollectable']}"
        )


def main() -> None:
    """Count references, leak a cycle, then collect it."""
    gc.collect()  # start from a clean heap
    gc.disable()  # no surprise collections while we count
    print("-- sys.getrefcount (3.14 borrows the argument: no +1)")
    data = [1, 2, 3]
    print("  new list      :", sys.getrefcount(data))
    alias = data
    print("  + alias       :", sys.getrefcount(data))
    holder = {"k": data}
    print("  + in a dict   :", sys.getrefcount(data))
    del alias, holder
    print("  after del both:", sys.getrefcount(data))
    print(
        "  None, 1, 'a'  :",
        sys.getrefcount(None) > 1000,
        sys.getrefcount(1) > 1000,
        "(immortal objects in 3.12+)",
    )
    print("-- refcount hits zero: freed at once")
    first = Node("a")
    probe = weakref.ref(first)
    del first
    print("  alive after del:", probe() is not None)
    print("-- a cycle: refcount never reaches zero")
    left, right = Node("left"), Node("right")
    left.other, right.other = right, left
    probe = weakref.ref(left)
    del left, right
    print("  alive after del:", probe() is not None)
    gc.callbacks.append(watch)
    collected = gc.collect()
    gc.callbacks.remove(watch)
    print("  gc.collect()   :", collected)
    print("  alive after gc :", probe() is not None)
    print("  callback saw   :", events)
    print("-- 100 cycles; the last pair is still named a and b")
    for _ in range(100):
        a, b = Node("a"), Node("b")
        a.other, b.other = b, a
    print("  gc.collect()   :", gc.collect(), "(2 * 100 - 2)")
    print("-- 3.14 note")
    print("  thresholds     :", gc.get_threshold())
    print("  generations    :", len(gc.get_stats()))
    print("  3.14.0-3.14.4 shipped an incremental collector;")
    print("  3.14.5+ reverted to the 3.13 generational one.")
    print("  running", sys.version.split()[0])
    gc.enable()


if __name__ == "__main__":
    main()
