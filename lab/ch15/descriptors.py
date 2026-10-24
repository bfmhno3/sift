"""Descriptors: functions, property, classmethod, staticmethod, cost."""

import statistics
import time
from collections.abc import Callable
from typing import Any

from sift.config import Config


class Greeter:
    """A class with one method of each kind."""

    def __init__(self, name: str) -> None:
        self._name = name

    def hello(self) -> str:
        return f"hello, {self._name}"

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    def anonymous(cls) -> Greeter:
        return cls("nobody")

    @staticmethod
    def shout(text: str) -> str:
        return text.upper()


class MyProperty:
    """A pure-Python property: a data descriptor."""

    def __init__(
        self,
        fget: Callable[[Any], Any],
        fset: Callable[[Any, Any], None] | None = None,
    ) -> None:
        self.fget = fget
        self.fset = fset
        self.__doc__ = fget.__doc__

    def setter(self, fset: Callable[[Any, Any], None]) -> MyProperty:
        return type(self)(self.fget, fset)

    def __get__(self, obj: object, owner: type | None = None) -> Any:
        if obj is None:
            return self
        return self.fget(obj)

    def __set__(self, obj: object, value: object) -> None:
        if self.fset is None:
            raise AttributeError("property has no setter")
        self.fset(obj, value)


class MyClassMethod:
    """A pure-Python classmethod: bind the class, not the instance."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func

    def __get__(self, obj: object, owner: type | None = None) -> Any:
        owner = owner or type(obj)
        return lambda *args: self.func(owner, *args)


class MyStaticMethod:
    """A pure-Python staticmethod: bind nothing."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func

    def __get__(self, obj: object, owner: type | None = None) -> Any:
        return self.func


class Clone:
    """The same shapes, built from the clones above."""

    def __init__(self) -> None:
        self._x = 1

    @MyProperty
    def x(self) -> int:
        """The x value."""
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self._x = value

    @MyClassMethod
    def make(cls) -> Clone:
        return cls()

    @MyStaticMethod
    def twice(value: int) -> int:
        return value * 2


class Plain:
    """Plain attributes, for the cost comparison."""

    def __init__(self) -> None:
        self.limit = 10


def per_op_ns(run: Callable[[], None], loops: int) -> float:
    """Return the nanoseconds of one iteration of run()."""
    start = time.perf_counter_ns()
    run()
    return (time.perf_counter_ns() - start) / loops


def main() -> None:
    """Show how each built-in descriptor binds, then time a Setting."""
    greeter = Greeter("ada")
    print("-- functions are non-data descriptors")
    func = vars(Greeter)["hello"]
    print("type in class dict :", type(func).__name__)
    print("has __get__        :", hasattr(func, "__get__"))
    print("has __set__        :", hasattr(func, "__set__"))
    bound = func.__get__(greeter, Greeter)
    print("func.__get__(obj)  :", type(bound).__name__)
    print("bound.__self__ is obj:", bound.__self__ is greeter)
    print("bound.__func__ is func:", bound.__func__ is func)
    print("Greeter.hello is func :", Greeter.hello is func)
    print("greeter.hello is bound:", greeter.hello is bound)
    greeter.__dict__["hello"] = lambda: "from the instance dict"
    print("instance dict wins     :", greeter.hello())
    del greeter.__dict__["hello"]
    print("-- property, classmethod, staticmethod")
    for name in ("name", "anonymous", "shout"):
        obj = vars(Greeter)[name]
        print(
            f"{name:10} {type(obj).__name__:13}"
            f" __get__={hasattr(obj, '__get__')}"
            f" __set__={hasattr(obj, '__set__')}"
        )
    try:
        greeter.name = "bob"
    except AttributeError as error:
        print("property without setter:", error)
    print("Greeter.anonymous().name:", Greeter.anonymous().name)
    print("greeter.shout('a')      :", greeter.shout("a"))
    print("-- the clones behave the same")
    clone = Clone()
    clone.x = 5
    print("clone.x       :", clone.x)
    print("Clone.x.__doc__:", Clone.x.__doc__)
    print("Clone.make()  :", type(Clone.make()).__name__)
    print("clone.twice(4):", clone.twice(4))
    print("-- what a Setting costs (ns per operation, 10 rounds)")
    config = Config()
    plain = Plain()
    loops = 200_000

    def empty() -> None:
        for _ in range(loops):
            pass

    def set_plain() -> None:
        for _ in range(loops):
            plain.limit = 20

    def set_setting() -> None:
        for _ in range(loops):
            config.limit = 20

    def get_plain() -> None:
        for _ in range(loops):
            _ = plain.limit

    def get_setting() -> None:
        for _ in range(loops):
            _ = config.limit

    runs = {
        "empty loop": empty,
        "set plain": set_plain,
        "set Setting": set_setting,
        "get plain": get_plain,
        "get Setting": get_setting,
    }
    samples: dict[str, list[float]] = {name: [] for name in runs}
    for _ in range(10):  # alternate, so the CPU state hits all of them
        for name, run in runs.items():
            samples[name].append(per_op_ns(run, loops))
    for name, values in samples.items():
        print(
            f"{name:12} min {min(values):6.1f}"
            f"  median {statistics.median(values):6.1f}"
        )


if __name__ == "__main__":
    main()
