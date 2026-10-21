"""Properties: computed attributes, validation, read-only fields."""


class Query:
    """A search query whose words are validated on assignment."""

    def __init__(self, text: str) -> None:
        """Set the text through the property so it is validated."""
        self.text = text

    @property
    def text(self) -> str:
        """Return the query text."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Store value stripped; reject an empty query."""
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        self._text = value

    @property
    def words(self) -> list[str]:
        """Return the words; computed on every access, never stored."""
        return self._text.split()

    @property
    def size(self) -> int:
        """Return the number of words (read-only)."""
        return len(self.words)


def main() -> None:
    """Exercise getter, setter, deleter-less and read-only access."""
    q = Query("  rust ownership ")
    print("text:", repr(q.text))
    print("words:", q.words, "size:", q.size)
    q.text = "kalman filter smoother"
    print("after assignment:", q.words, q.size)
    try:
        q.text = "   "
    except ValueError as exc:
        print("empty text ->", exc)
    try:
        q.size = 5  # type: ignore[misc]
    except AttributeError as exc:
        print("size = 5 ->", exc)
    print("vars(q):", vars(q))
    print("type(Query.text):", type(Query.text).__name__)
    print("Query.text.fget:", Query.text.fget.__name__)
    print("Query.size.fset:", Query.size.fset)


if __name__ == "__main__":
    main()
