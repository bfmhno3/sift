"""FastAPI dependencies: Depends, Annotated, yield and overrides.

A route declares what it needs in its signature; FastAPI builds those
things per request, calls the dependencies they need first, and runs
the part of a ``yield`` dependency after the response. A test swaps a
dependency with ``app.dependency_overrides`` without touching the
route. The app is driven with TestClient, so nothing listens.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

EVENTS: list[str] = []


class Paging:
    """A class as a dependency: __init__ takes the query parameters."""

    def __init__(self, page: int = 1, size: int = 10) -> None:
        """Turn page and size into an offset and a limit."""
        self.offset = (page - 1) * size
        self.limit = size


def get_index() -> Iterator[list[str]]:
    """Open the 'index' for one request; close it after the response."""
    EVENTS.append("open")
    try:
        yield ["tea", "river", "bicycle", "compiler", "bridges"]
    finally:
        EVENTS.append("close")


def get_user(index: Annotated[list[str], Depends(get_index)]) -> str:
    """A dependency of a dependency: FastAPI resolves index first."""
    return f"reader of {len(index)} posts"


Index = Annotated[list[str], Depends(get_index)]
# Depends() with no argument means the class of the annotation
PagingDep = Annotated[Paging, Depends()]
UserDep = Annotated[str, Depends(get_user)]

app = FastAPI()


@app.get("/posts")
def posts(index: Index, paging: PagingDep, user: UserDep) -> dict[str, object]:
    """List a page of posts."""
    page = index[paging.offset : paging.offset + paging.limit]
    return {"user": user, "offset": paging.offset, "posts": page}


def main() -> None:
    """Call the route, then call it with an overridden dependency."""
    with TestClient(app) as client:
        print(client.get("/posts?page=2&size=2").json())
        print("events after one request:", EVENTS)
        print(client.get("/posts?size=x").json()["detail"][0]["msg"])

        def two_posts() -> Iterator[list[str]]:
            yield ["only", "two"]

        app.dependency_overrides[get_index] = two_posts
        print(client.get("/posts").json())
        app.dependency_overrides.clear()
    print("events at the end:", EVENTS)


if __name__ == "__main__":
    main()
