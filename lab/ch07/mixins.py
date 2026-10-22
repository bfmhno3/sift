"""Mixins: small classes that add one behaviour to others."""

import json
from collections.abc import Iterator


class JsonMixin:
    """Add to_json() to any class with a __dict__."""

    def to_json(self) -> str:
        """Return the instance attributes as sorted JSON."""
        return json.dumps(vars(self), sort_keys=True, ensure_ascii=False)


class ReprMixin:
    """Add a __repr__ built from the instance attributes."""

    def __repr__(self) -> str:
        """Return ClassName(attr=value, ...)."""
        fields = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{type(self).__name__}({fields})"


class CountMixin:
    """Count instances per concrete class, via cooperative super()."""

    counts: dict[str, int] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Count, then pass every argument on along the MRO."""
        name = type(self).__name__
        CountMixin.counts[name] = CountMixin.counts.get(name, 0) + 1
        super().__init__(*args, **kwargs)


class Hit:
    """A search hit: a title and a score."""

    def __init__(self, title: str, score: float) -> None:
        """Store the fields."""
        self.title = title
        self.score = score


class RichHit(CountMixin, ReprMixin, JsonMixin, Hit):
    """Hit plus three mixins; mixins come first, the real base last."""


class Hits(list[RichHit]):
    """A list subclass; list is itself a base like any other."""

    def titles(self) -> Iterator[str]:
        """Yield the titles."""
        return (hit.title for hit in self)


def main() -> None:
    """Build a few hits and show what each mixin contributed."""
    hits = Hits([RichHit("Kalman", 2.5), RichHit("卡尔曼", 1.0)])
    print(hits[0])
    print(hits[1].to_json())
    print("titles:", list(hits.titles()))
    print("counts:", CountMixin.counts)
    print("MRO:", [c.__name__ for c in RichHit.__mro__])


if __name__ == "__main__":
    main()
