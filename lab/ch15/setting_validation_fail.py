"""Assign limit = 0 to a Config: the descriptor refuses."""

from sift.config import Config


def main() -> None:
    """Set limit to a value below the minimum of 1."""
    config = Config()
    # error: sift.errors.ConfigError: [search] limit must be an integer
    # between 1 and 100
    config.limit = 0
    print("unreachable:", config.limit)


if __name__ == "__main__":
    main()
