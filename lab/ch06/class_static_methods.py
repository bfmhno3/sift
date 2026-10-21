"""classmethod, staticmethod and alternate constructors."""

from pathlib import Path

from sift.document import Document


class Version:
    """A version number with alternate constructors."""

    def __init__(self, major: int, minor: int) -> None:
        """Store the two numbers."""
        self.major = major
        self.minor = minor

    @classmethod
    def parse(cls, text: str) -> Version:
        """Build a Version from ``"3.14"``; cls follows subclasses."""
        major, minor = text.split(".")
        return cls(int(major), int(minor))

    @staticmethod
    def is_valid(text: str) -> bool:
        """Return True for ``digits.digits``; needs no instance."""
        major, dot, minor = text.partition(".")
        return bool(dot) and major.isdigit() and minor.isdigit()

    def __repr__(self) -> str:
        """Return the constructor-style form."""
        return f"{type(self).__name__}({self.major}, {self.minor})"


class Python(Version):
    """A subclass: parse() builds a Python, not a Version."""


def main() -> None:
    """Show both decorators, then Document.from_markdown."""
    print("Version.parse('3.14'):", Version.parse("3.14"))
    print("Python.parse('3.14'):", Python.parse("3.14"))
    print("is_valid:", Version.is_valid("3.14"), Version.is_valid("3."))
    print("Version.parse:", Version.parse)
    print("Version.is_valid:", Version.is_valid)
    print("same function via an instance:", Version(1, 0).is_valid("1.0"))

    path = Path("tests/fixtures/mini/tea-brewing.md")
    doc = Document.from_markdown(0, path, path.read_text(encoding="utf-8"))
    print("title:", doc.title)
    print("published:", doc.published.isoformat())
    print("tags:", doc.tags, "category:", doc.category)
    print("body starts:", repr(doc.body[:30]))


if __name__ == "__main__":
    main()
