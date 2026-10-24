"""Annotations at run time: lazy in 3.14, readable, never enforced."""

import annotationlib
from annotationlib import Format
from typing import cast, get_type_hints


class Node:
    """A class that mentions itself and a name defined later."""

    parent: Node | None
    weight: Weight

    def link(self, other: Node) -> Node:
        """Return other."""
        return other


class Weight(float):
    """Defined after Node: 3.14 evaluates annotations lazily."""


def double(x: int) -> int:
    """Return twice x."""
    return x * 2


def main() -> None:
    """Read annotations in each format; call with a wrong type."""
    print(annotationlib.get_annotations(double))
    print(annotationlib.get_annotations(Node, format=Format.STRING))
    print(annotationlib.get_annotations(Node, format=Format.FORWARDREF))
    print(get_type_hints(Node))
    print(double.__annotations__)
    print(double(cast("int", "ab")))  # cast tells the checker a lie
    node = Node()
    node.weight = cast("Weight", "heavy")
    print(node.weight)


if __name__ == "__main__":
    main()
