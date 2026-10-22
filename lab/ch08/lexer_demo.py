"""The lexer is a generator: tokens come out one at a time."""

from sift.query import iter_tokens

QUERIES = [
    'tag:Rust "device tree" -latex',
    "(pid OR kalman) AND filter*",
    "state-of-the-art and or NOT",
]


def main() -> None:
    """Print the tokens of three queries and step one by hand."""
    for query in QUERIES:
        print(repr(query))
        for token in iter_tokens(query):
            print(f"  {token.pos:>2}  {token.kind.name:<6} {token.text!r}")
    stream = iter_tokens("a OR b")
    print(type(stream).__name__, next(stream), next(stream))


if __name__ == "__main__":
    main()
