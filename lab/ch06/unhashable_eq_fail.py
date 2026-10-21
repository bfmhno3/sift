"""A class that defines __eq__ alone cannot be a set member."""


class Doc:
    """Equal by doc_id, but with no __hash__."""

    def __init__(self, doc_id: int) -> None:
        """Store the id."""
        self.doc_id = doc_id

    def __eq__(self, other: object) -> bool:
        """Compare by doc_id."""
        if not isinstance(other, Doc):
            return NotImplemented
        return self.doc_id == other.doc_id


def main() -> None:
    """Put a Doc in a set."""
    # error: TypeError: cannot use 'Doc' as a set element (unhashable
    # type: 'Doc')
    print({Doc(1)})


if __name__ == "__main__":
    main()
