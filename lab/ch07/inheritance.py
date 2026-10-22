"""Overriding, super() and attribute lookup through a hierarchy."""


class Tokenizer:
    """Split text on whitespace."""

    name = "whitespace"

    def __init__(self, lowercase: bool = False) -> None:
        """Remember whether to lowercase."""
        self.lowercase = lowercase

    def tokens(self, text: str) -> list[str]:
        """Return the whitespace-separated words of text."""
        if self.lowercase:
            text = text.lower()
        return text.split()

    def describe(self) -> str:
        """Return a one-line description."""
        return f"{type(self).__name__}({self.name})"


class CommaTokenizer(Tokenizer):
    """Override tokens() to split on commas, reuse the rest."""

    name = "comma"

    def tokens(self, text: str) -> list[str]:
        """Return comma-separated fields, stripped."""
        parts = text.split(",")
        return [part.strip() for part in parts]


class LoudTokenizer(Tokenizer):
    """Extend __init__ and tokens() through super()."""

    def __init__(self, shout: str = "!") -> None:
        """Call the parent __init__ first, then add own state."""
        super().__init__(lowercase=True)
        self.shout = shout

    def tokens(self, text: str) -> list[str]:
        """Return the parent's tokens with a suffix on each."""
        return [word + self.shout for word in super().tokens(text)]


def main() -> None:
    """Show which method runs and where attributes are found."""
    text = "Red, Green Blue"
    for tok in (Tokenizer(), CommaTokenizer(), LoudTokenizer()):
        print(f"{tok.describe():32} {tok.tokens(text)}")
    loud = LoudTokenizer()
    print("instance dict:", vars(loud))
    owners = [c.__name__ for c in type(loud).__mro__ if "name" in vars(c)]
    print("name found on:", owners)
    print("issubclass:", issubclass(LoudTokenizer, Tokenizer))
    print("isinstance:", isinstance(loud, Tokenizer))
    print("isinstance, reversed:", isinstance(Tokenizer(), LoudTokenizer))
    print(
        "describe is inherited:", LoudTokenizer.describe is Tokenizer.describe
    )
    print("tokens is the parent's:", LoudTokenizer.tokens is Tokenizer.tokens)


if __name__ == "__main__":
    main()
