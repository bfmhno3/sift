"""Implement three methods of Mapping, get the rest for free."""

from collections.abc import Iterator, Mapping


class Upper(Mapping[str, int]):
    """A read-only copy of a dict with upper-cased keys."""

    def __init__(self, data: dict[str, int]) -> None:
        """Store the data under upper-cased keys."""
        self._data = {k.upper(): v for k, v in data.items()}

    def __getitem__(self, key: str) -> int:
        """Return the value of key, ignoring case."""
        return self._data[key.upper()]

    def __iter__(self) -> Iterator[str]:
        """Iterate over the upper-cased keys."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return the number of keys."""
        return len(self._data)


def main() -> None:
    """Call every method that Mapping provides."""
    view = Upper({"tea": 3, "River": 5})
    mine = ("__getitem__", "__iter__", "__len__", "__contains__", "get")
    print("own methods :", [n for n in mine if n in vars(Upper)])
    print("keys()      :", list(view.keys()))
    print("values()    :", list(view.values()))
    print("items()     :", list(view.items()))
    print("get         :", view.get("tea"), view.get("none", -1))
    print("in          :", "river" in view, "bicycle" in view)
    print("==          :", view == {"TEA": 3, "RIVER": 5})
    print("dict(view)  :", dict(view))
    inherited = [
        name
        for name in (
            "keys",
            "items",
            "values",
            "get",
            "__contains__",
            "__eq__",
        )
        if name not in vars(Upper)
    ]
    print("inherited   :", inherited)
    print("MRO         :", [c.__name__ for c in Upper.__mro__])
    try:
        view["x"] = 1  # type: ignore[index]
    except TypeError as exc:
        print("TypeError   :", exc)

    from sift.index import InvertedIndex

    print("InvertedIndex is a Mapping:", issubclass(InvertedIndex, Mapping))
    own = [
        n
        for n in ("__getitem__", "__iter__", "__len__", "keys", "get")
        if n in vars(InvertedIndex)
    ]
    print("defined on InvertedIndex:", own)


if __name__ == "__main__":
    main()
