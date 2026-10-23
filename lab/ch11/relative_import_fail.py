"""A relative import in a file run as a script fails (expected)."""

# error: ImportError: attempted relative import with no known parent
# package
from .relative_imports import a


def main() -> None:
    """Use the import, so the failure is the only thing in the way."""
    print(a.double(1))


if __name__ == "__main__":
    main()
