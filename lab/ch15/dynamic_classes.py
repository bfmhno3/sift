"""Classes made at run time: type, new_class, make_dataclass, Enum."""

import types
from collections import namedtuple
from dataclasses import fields, make_dataclass
from enum import Enum

from sift.config import Setting, Settings


class Base:
    def hello(self) -> str:
        return f"hello from {type(self).__name__}"


def main() -> None:
    """Build the same kinds of class without a class statement."""
    print("-- type(name, bases, ns)")
    ns = {"x": 1, "double": lambda self: self.x * 2}
    made = type("Made", (Base,), ns)
    print(" ", made.__name__, made().double(), made().hello())
    print("-- types.new_class runs the whole protocol")
    steps: list[str] = []
    cls = types.new_class(
        "Fresh", (Base,), exec_body=lambda body: steps.append("body")
    )
    print(" ", cls.__mro__[:2], steps)
    print("-- __set_name__ and __init_subclass__ work too")
    tiny = type(
        "Tiny",
        (Settings,),
        {"size": Setting(int, default=3, min=1, section="tiny")},
    )
    print(" ", tiny.size.name, list(tiny._settings), tiny(size=9))
    print("-- make_dataclass, namedtuple, Enum")
    point = make_dataclass("Point", [("x", int), ("y", int, 0)])
    print(" ", point(1), [f.name for f in fields(point)])
    pair = namedtuple("pair", ["left", "right"])
    print(" ", pair(1, 2))
    color = Enum("Color", "RED GREEN")
    print(" ", list(color), color.RED.value)
    print("-- patching a class after creation")
    made.shout = lambda self: "HEY"  # type: ignore[attr-defined]
    print(" ", made().shout())
    print("-- changing __class__ of a live object")
    obj = made()
    obj.__class__ = Base
    print(" ", obj.hello(), hasattr(obj, "x"))
    print("-- types.SimpleNamespace and MappingProxyType")
    space = types.SimpleNamespace(a=1)
    space.b = 2
    print(" ", space)
    try:
        made.__dict__["x"] = 2  # type: ignore[index]
    except TypeError as error:
        print(" ", error)


if __name__ == "__main__":
    main()
