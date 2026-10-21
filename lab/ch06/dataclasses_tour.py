"""dataclasses: field, frozen, order, slots, kw_only, replace."""

from dataclasses import (
    asdict,
    dataclass,
    field,
    fields,
    replace,
)


@dataclass
class Bag:
    """Mutable defaults need default_factory, not ``= []``."""

    name: str
    terms: list[str] = field(default_factory=list)
    seen: int = field(default=0, repr=False, compare=False)


@dataclass(frozen=True, order=True)
class Version:
    """Frozen, hashable, and ordered field by field."""

    major: int
    minor: int = 0


@dataclass(slots=True, kw_only=True)
class Config:
    """Every argument must be passed by keyword."""

    k1: float = 1.2
    b: float = 0.75
    limit: int = 10


@dataclass
class Span:
    """Derived data and validation in __post_init__."""

    start: int
    end: int
    length: int = field(init=False)

    def __post_init__(self) -> None:
        """Validate the bounds and compute length."""
        if self.end < self.start:
            raise ValueError(f"end {self.end} < start {self.start}")
        self.length = self.end - self.start


def main() -> None:
    """Show what each option generates."""
    a, b = Bag("a"), Bag("b")
    a.terms.append("x")
    print("separate lists:", a.terms, b.terms)
    print("generated repr:", a)
    print("eq ignores 'seen':", Bag("a", ["x"], 5) == Bag("a", ["x"], 9))
    print("fields:", [f.name for f in fields(Bag)])

    v = Version(3, 14)
    print("order:", Version(3, 9) < v < Version(4), sorted([v, Version(2)]))
    print("hashable:", hash(v) == hash(Version(3, 14)), {v, Version(3, 14)})
    print("replace:", replace(v, minor=15), "original:", v)
    print("asdict:", asdict(Bag("c", ["t"])))

    cfg = Config(limit=5)
    print("kw_only:", cfg)
    try:
        Config(1.5)  # type: ignore[misc]
    except TypeError as exc:
        print("positional ->", exc)
    print("slots, no __dict__:", not hasattr(cfg, "__dict__"))

    print("post_init:", Span(2, 9))
    try:
        Span(9, 2)
    except ValueError as exc:
        print("bad span ->", exc)
    print(
        "generated methods:",
        sorted(
            n
            for n in vars(Version)
            if n in {"__init__", "__repr__", "__eq__", "__lt__", "__hash__"}
        ),
    )


if __name__ == "__main__":
    main()
