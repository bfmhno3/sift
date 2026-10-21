"""Annotations in 3.14: deferred evaluation and annotationlib."""

import annotationlib
from annotationlib import Format


class Node:
    """A tree node; the annotation names a class not yet defined."""

    def __init__(self, parent: Node | None, kids: list[Node]) -> None:
        self.parent = parent
        self.kids = kids


def link(a: Node, b: Missing) -> Missing:  # noqa: F821
    """Annotate with a name that never exists."""
    return b


def main() -> None:
    """Read annotations in each format."""
    # 3.14 起注解延迟求值：Node 在方法定义时还不存在，也不需要引号
    print(Node.__init__.__annotations__)
    print(annotationlib.get_annotations(Node.__init__))

    # Missing 从未定义；VALUE 格式求值会失败，另外两种不会
    try:
        print(link.__annotations__)
    except NameError as exc:
        print(f"NameError: {exc}")
    fwd = annotationlib.get_annotations(link, format=Format.FORWARDREF)
    print(fwd)
    print(type(fwd["b"]).__name__)
    print(annotationlib.get_annotations(link, format=Format.STRING))

    print(Node.__init__.__annotate__ is not None)
    print(annotationlib.get_annotations(Node.__init__, format=Format.STRING))


if __name__ == "__main__":
    main()
