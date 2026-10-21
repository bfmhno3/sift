"""__new__ creates the object, __init__ fills it in."""


class Loud:
    """Print each step of the construction protocol."""

    def __new__(cls, name: str) -> Loud:
        """Allocate the instance; runs before __init__."""
        print(f"__new__({cls.__name__}, {name!r})")
        return super().__new__(cls)

    def __init__(self, name: str) -> None:
        """Initialize the instance that __new__ returned."""
        print(f"__init__({name!r})")
        self.name = name


class Interned:
    """Return one shared instance per name, decided in __new__."""

    _cache: dict[str, Interned] = {}

    def __new__(cls, name: str) -> Interned:
        """Return the cached instance for name, creating it once."""
        if name not in cls._cache:
            obj = super().__new__(cls)
            obj.name = name
            cls._cache[name] = obj
        return cls._cache[name]


def main() -> None:
    """Show the order of calls and a __new__ that returns a cache."""
    obj = Loud("x")
    print("result:", type(obj).__name__, obj.name)
    print("Interned('a') is Interned('a'):", Interned("a") is Interned("a"))
    print("Interned('a') is Interned('b'):", Interned("a") is Interned("b"))


if __name__ == "__main__":
    main()
