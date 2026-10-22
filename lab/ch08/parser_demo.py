"""Parse six queries and print the syntax trees."""

from sift.query import parse

QUERIES = [
    "kalman filter",
    "pid AND 积分",
    "矩阵 OR matrix",
    "typst -latex",
    'tag:Rust "device tree" OR title:parser',
    "a OR b c NOT (d OR e*)",
]


def main() -> None:
    """Show how juxtaposition, OR, NOT and parentheses bind."""
    for query in QUERIES:
        print(query)
        print("  ", parse(query))


if __name__ == "__main__":
    main()
