"""object.__getattribute__: the lookup order, written out in Python."""

from typing import Any

_MISSING = object()


class Data:
    """A data descriptor: it defines __get__ and __set__."""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: object, owner: type | None = None) -> str:
        return f"Data.__get__({self.name})"

    def __set__(self, obj: object, value: object) -> None:
        print(f"  Data.__set__({self.name}, {value!r})")


class NonData:
    """A non-data descriptor: __get__ only."""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: object, owner: type | None = None) -> str:
        return f"NonData.__get__({self.name})"


class Demo:
    """Every step of the lookup has a witness here."""

    data = Data()
    nondata = NonData()
    plain = "class attribute"

    def __init__(self) -> None:
        # __dict__ writes bypass __set__ and show who wins on reads
        self.__dict__["data"] = "instance dict"
        self.__dict__["nondata"] = "instance dict"
        self.__dict__["plain"] = "instance dict"

    def __getattr__(self, name: str) -> str:
        return f"__getattr__({name})"


def lookup(obj: object, name: str) -> Any:
    """Re-implement object.__getattribute__ (without slots)."""
    cls = type(obj)
    found: Any = _MISSING
    for base in cls.__mro__:
        if name in vars(base):
            found = vars(base)[name]
            break
    if found is not _MISSING and hasattr(type(found), "__set__"):
        # 1. data descriptor
        return type(found).__get__(found, obj, cls)
    if name in vars(obj):
        return vars(obj)[name]  # 2. instance dict
    if found is not _MISSING:
        if hasattr(type(found), "__get__"):
            return type(found).__get__(found, obj, cls)  # 3. non-data
        return found  # 4. plain class attribute
    getter = getattr(cls, "__getattr__", None)
    if getter is not None:
        return getter(obj, name)  # 5. __getattr__
    raise AttributeError(name)


class Traced:
    """Override __getattribute__: it sees every access, even methods."""

    seen: list[str] = []

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("__"):
            Traced.seen.append(name)
        return super().__getattribute__(name)

    def method(self) -> int:
        return self.value + 1

    value = 41


def main() -> None:
    """Print each step of the lookup order."""
    demo = Demo()
    print("1. data descriptor on the type beats the instance dict")
    print("  ", demo.data)
    demo.data = "assigned"
    print("  instance dict still holds:", vars(demo)["data"])
    print("2. instance dict beats a non-data descriptor")
    print("  ", demo.nondata)
    print("  ", demo.plain)
    print("3. delete the dict entries: the class side shows through")
    del demo.__dict__["nondata"]
    del demo.__dict__["plain"]
    print("  ", demo.nondata)
    print("  ", demo.plain)
    print("4. nothing found: __getattr__ is the last resort")
    print("  ", demo.missing)
    print("lookup() agrees with getattr on every name:")
    for name in ("data", "nondata", "plain", "missing"):
        same = lookup(demo, name) == getattr(demo, name)
        print(f"  {name:8} {same}")
    print("__getattribute__ override sees method and data access")
    traced = Traced()
    print("  ", traced.method())
    print("  ", Traced.seen)


if __name__ == "__main__":
    main()
