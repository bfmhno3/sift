"""__del__: when it runs, what it cannot do, how to avoid it."""

import gc
import sys
from types import TracebackType
from typing import Any


class Loud:
    """Announce destruction."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print(f"  __del__({self.name})")


class Broken:
    """__del__ that raises: the exception cannot propagate."""

    def __del__(self) -> None:
        raise RuntimeError("boom in __del__")


class Phoenix:
    """__del__ that stores self: resurrection."""

    graveyard: list[Phoenix] = []

    def __del__(self) -> None:
        print("  __del__(Phoenix) resurrects the object")
        Phoenix.graveyard.append(self)


class Closing:
    """The better way: a context manager releases deterministically."""

    def __enter__(self) -> Closing:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        print("  closed in __exit__")


def main() -> None:
    """Run each pitfall in turn."""
    gc.collect()
    gc.disable()
    print("-- del x only unbinds a name")
    a = Loud("a")
    b = a
    del a
    print("  after del a: still reachable through b")
    del b
    print("-- exceptions in __del__ go to sys.unraisablehook")
    seen: list[str] = []

    def hook(arg: Any) -> None:
        seen.append(f"{arg.exc_type.__name__}: {arg.exc_value}")

    old = sys.unraisablehook
    sys.unraisablehook = hook
    Broken()
    sys.unraisablehook = old
    print("  captured:", seen)
    print("-- a cycle with __del__ is collected since PEP 442")
    one, two = Loud("one"), Loud("two")
    one.other, two.other = two, one  # type: ignore[attr-defined]
    del one, two
    print("  before gc.collect()")
    print("  collected:", gc.collect())
    print("-- resurrection: __del__ runs once, the object lives on")
    Phoenix()
    print("  graveyard:", len(Phoenix.graveyard))
    Phoenix.graveyard.clear()
    print("  cleared; __del__ does not run again:", gc.collect() >= 0)
    print("-- the deterministic alternative")
    with Closing():
        print("  inside the block")
    gc.enable()


if __name__ == "__main__":
    main()
