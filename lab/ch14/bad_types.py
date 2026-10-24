"""Six type errors that run fine: annotations are not enforced."""

from typing import Protocol, TypedDict


class Titled(Protocol):
    """Anything with a title() method."""

    def title(self) -> str:
        """Return the title."""
        ...


class Post(TypedDict):
    """A post with a title and a view count."""

    title: str
    views: int


class NoTitle:
    """Has no title() method."""

    name = "no title"


def double(n: int) -> int:
    """Return twice n."""
    return n * 2


def find(words: list[str], prefix: str) -> str | None:
    """Return the first word that starts with prefix, or None."""
    for word in words:
        if word.startswith(prefix):
            return word
    return None


def count(words: list[str]) -> int:
    """Return how many words there are."""
    # error: return-value: Incompatible return value type (got "str",
    # expected "int")
    return str(len(words))


def mean(values: list[float]) -> float:
    """Return the mean of values."""
    return sum(values) / len(values)


def show(item: Titled) -> str:
    """Return the title of item."""
    return item.title()


def main() -> None:
    """Run all six mistakes; Python does not stop any of them."""
    # error: arg-type: Argument 1 to "double" has incompatible type
    # "str"; expected "int"
    print(double("ab"))
    # error: union-attr: Item "None" of "str | None" has no attribute
    # "upper"
    print(find(["tea", "tar"], "ta").upper())
    print(count(["a", "b"]))
    post: Post = {"title": "tea", "views": 3}
    # error: typeddict-unknown-key: TypedDict "Post" has no key "view"
    post["view"] = 4
    print(post)
    ints: list[int] = [1, 2, 3]
    # error: arg-type: Argument 1 to "mean" has incompatible type
    # "list[int]"; expected "list[float]"
    print(mean(ints))
    try:
        # error: arg-type: Argument 1 to "show" has incompatible type
        # "NoTitle"; expected "Titled"
        print(show(NoTitle()))
    except AttributeError as exc:
        print("AttributeError:", exc)


if __name__ == "__main__":
    main()
