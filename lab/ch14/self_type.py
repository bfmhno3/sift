"""Self: methods that return the type of the instance they run on."""

from typing import Self, reveal_type


class Builder:
    """A fluent builder; subclasses keep their own type in chains."""

    def __init__(self) -> None:
        """Start with no parts."""
        self.parts: list[str] = []

    def add(self, part: str) -> Self:
        """Append part and return the same object."""
        self.parts.append(part)
        return self

    @classmethod
    def of(cls, *parts: str) -> Self:
        """Build an instance of the class it is called on."""
        built = cls()
        for part in parts:
            built.add(part)
        return built

    def copy(self) -> Self:
        """Return a new object of the same class with the same parts."""
        return type(self).of(*self.parts)


class QueryBuilder(Builder):
    """Adds methods that the base class does not have."""

    def and_(self, word: str) -> Self:
        """Join word with AND."""
        return self.add("AND").add(word)


def main() -> None:
    """Chain calls: the checker knows every step is a QueryBuilder."""
    query = QueryBuilder.of("rust").and_("lifetime").and_("borrow")
    print(" ".join(query.parts), type(query.copy()).__name__)
    reveal_type(query.add("x"))
    reveal_type(QueryBuilder.of())


if __name__ == "__main__":
    main()
