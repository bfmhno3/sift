"""enum: Enum, auto, IntFlag and StrEnum."""

from enum import Enum, IntFlag, StrEnum, auto


class Field(StrEnum):
    """Searchable fields; members are str and compare to str."""

    TITLE = auto()
    TAG = auto()
    CATEGORY = auto()
    SERIES = auto()


class Kind(Enum):
    """A plain enum: members are singletons, not ints or strs."""

    WORD = auto()
    PHRASE = auto()
    PREFIX = auto()


class Perm(IntFlag):
    """Bit flags: members combine with | and test with &."""

    READ = auto()
    WRITE = auto()
    EXEC = auto()


def main() -> None:
    """Show names, values, lookup, iteration and combination."""
    print("Kind.WORD:", Kind.WORD, repr(Kind.WORD))
    print("name, value:", Kind.WORD.name, Kind.WORD.value)
    print("by value:", Kind(2), "by name:", Kind["PREFIX"])
    print("iteration:", list(Kind))
    print("identity:", Kind(1) is Kind.WORD)
    print("Kind.WORD == 1:", Kind.WORD == 1)
    try:
        Kind(9)
    except ValueError as exc:
        print("Kind(9) ->", exc)

    print("StrEnum:", Field.TAG, repr(Field.TAG), Field.TAG == "tag")
    print("lookup from text:", Field("category"))
    print("f-string:", f"{Field.TITLE}:rust")

    rw = Perm.READ | Perm.WRITE
    print("IntFlag:", rw, int(rw), repr(rw))
    print("has WRITE:", bool(rw & Perm.WRITE), "has EXEC:", Perm.EXEC in rw)
    print("all flags:", Perm.READ | Perm.WRITE | Perm.EXEC)
    print("rw & ~WRITE:", rw & ~Perm.WRITE)
    print("rw == 3:", rw == 3)


if __name__ == "__main__":
    main()
