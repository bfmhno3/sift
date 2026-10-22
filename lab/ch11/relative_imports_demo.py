"""Relative and absolute imports inside one package."""

import sys

import relative_imports
from relative_imports import a, b


def main() -> None:
    """Show where each name comes from and what the dots resolve to."""
    print("package:", relative_imports.__name__)
    print("a.__package__:", a.__package__)
    print("b.__package__:", b.__package__)
    print("double(5) =", relative_imports.double(5))
    print("same b object:", a.OFFSET == b.OFFSET)
    print("a.ABSOLUTE_OFFSET:", a.ABSOLUTE_OFFSET)
    print("__init__ exports:", relative_imports.__all__)
    loaded = [n for n in sys.modules if n.startswith("relative_imports.")]
    print("submodules loaded:", sorted(loaded))


if __name__ == "__main__":
    main()
