"""Build a model from bad data: pydantic.ValidationError.

First the error as data (``errors()``, ``error_count()``), then the
same call again without a ``try``: the exception ends the script with
its multi-line message and a non-zero exit status.
"""

from pydantic import BaseModel, Field, ValidationError


class SearchRequest(BaseModel):
    """What a client may ask: a non-blank query and 1 to 100 hits."""

    q: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    page: int = 1


BAD = {"q": "", "limit": "lots", "page": 2.5}


def main() -> None:
    """Show the error twice: as data, then uncaught."""
    try:
        SearchRequest(**BAD)
    except ValidationError as error:
        print(f"{error.error_count()} errors")
        for problem in error.errors(include_url=False):
            print(" ", problem["loc"], problem["type"], "-", problem["msg"])
    # error: pydantic_core.ValidationError: 3 validation errors
    SearchRequest(**BAD)
    print("unreachable")


if __name__ == "__main__":
    main()
