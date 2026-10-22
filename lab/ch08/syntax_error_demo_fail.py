"""An unbalanced parenthesis: the parser's exception, uncaught."""

# error: sift.query.errors.QuerySyntaxError: expected ')'

from sift.query import parse


def main() -> None:
    """Parse a query that never closes its parenthesis."""
    parse("(kalman OR pid filter")


if __name__ == "__main__":
    main()
