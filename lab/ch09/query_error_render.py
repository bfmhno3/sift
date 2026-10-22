"""Caret output of QuerySyntaxError.render() for four bad queries."""

from sift.errors import QuerySyntaxError
from sift.query import parse

BAD_QUERIES = [
    "(rust",
    '"device tree',
    "rust AND",
    "(奇异 值",
    "-latex",
    "tag: rust",
]


def main() -> None:
    """Parse each bad query and print the rendered error."""
    for query in BAD_QUERIES:
        try:
            parse(query)
        except QuerySyntaxError as error:
            print(f"query    {query!r}")
            print(f"position {error.position}")
            print(error.render())
            print()


if __name__ == "__main__":
    main()
