"""Python clients of the Sift HTTP API, on httpx.

``SiftClient`` blocks; ``AsyncSiftClient`` is the same over
``httpx.AsyncClient``. Both talk to ``sift serve`` (FastAPI) and to
``sift serve --raw``, which have one contract, and return the pydantic
models of ``sift.server.models``::

    with SiftClient("http://127.0.0.1:8000") as client:
        result = client.search("rust lifetime", limit=3)

    async with AsyncSiftClient("http://127.0.0.1:8000") as client:
        result = await client.search("rust lifetime", limit=3)

A client keeps one connection pool for its life, so use it as a
context manager and share it. Errors:

* ``QuerySyntaxError``: 400 for a malformed query, with the query and
  the position, as ``sift search`` raises it.
* ``ApiError``: any other answer that is not 200, with the status and
  the message of the server.
* ``httpx.TransportError`` (``ConnectError``, ``ReadTimeout`` ...):
  the server did not answer; ``timeout`` bounds each phase of a
  request (connect, write, read, pool), 10 s by default.

The import of this module needs the ``web`` extra (httpx, pydantic).
"""

from http import HTTPStatus
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ValidationError

from sift.errors import QuerySyntaxError, SiftError
from sift.server.models import (
    DocumentResponse,
    ErrorResponse,
    HealthResponse,
    SearchResponse,
)

TIMEOUT = 10.0  # seconds, for each of connect, write, read and pool


class ApiError(SiftError):
    """The server answered with a status other than 200.

    status is the HTTP status; str(error) is the message of the
    server, or the reason phrase if the body has no ``error`` key.
    """

    def __init__(self, status: int, message: str) -> None:
        """Keep the status and the message."""
        super().__init__(status, message)
        self.status = status
        self.message = message

    def __str__(self) -> str:
        """Return ``<status>: <message>``."""
        return f"{self.status}: {self.message}"


def check(response: httpx.Response) -> None:
    """Raise the exception that response stands for, if it is one.

    QuerySyntaxError for a 400 that carries a query and a position,
    ApiError for any other status that is not 200.
    """
    if response.status_code == HTTPStatus.OK:
        return
    try:
        body = ErrorResponse.model_validate_json(response.content)
    except ValidationError:
        raise ApiError(response.status_code, response.reason_phrase) from None
    if body.query is not None and body.position is not None:
        raise QuerySyntaxError(body.error, body.query, body.position)
    raise ApiError(response.status_code, body.error)


def parse[M: BaseModel](model: type[M], response: httpx.Response) -> M:
    """Return the body of a 200 response as model; else raise."""
    check(response)
    return model.model_validate_json(response.content)


def search_params(query: str, limit: int | None) -> dict[str, str]:
    """Return the query string parameters of a search."""
    params = {"q": query}
    if limit is not None:
        params["limit"] = str(limit)
    return params


class SiftClient:
    """Blocking client of one Sift server."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Connect lazily to base_url, e.g. ``http://127.0.0.1:8000``.

        transport replaces the network (tests pass
        ``httpx.MockTransport``).
        """
        self.http = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )

    def __enter__(self) -> Self:
        """Return the client."""
        self.http.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connections."""
        self.http.__exit__(exc_type, exc, tb)

    def close(self) -> None:
        """Close the connections."""
        self.http.close()

    def health(self) -> HealthResponse:
        """Return ``GET /health``."""
        return parse(HealthResponse, self.http.get("/health"))

    def search(self, query: str, limit: int | None = None) -> SearchResponse:
        """Return ``GET /search``; limit defaults to the server's."""
        response = self.http.get("/search", params=search_params(query, limit))
        return parse(SearchResponse, response)

    def document(self, doc_id: int) -> DocumentResponse:
        """Return ``GET /docs/<doc_id>``."""
        return parse(DocumentResponse, self.http.get(f"/docs/{doc_id}"))


class AsyncSiftClient:
    """Asynchronous client of one Sift server."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Connect lazily to base_url, e.g. ``http://127.0.0.1:8000``.

        transport replaces the network (tests pass
        ``httpx.MockTransport``).
        """
        self.http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        """Return the client."""
        await self.http.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connections."""
        await self.http.__aexit__(exc_type, exc, tb)

    async def aclose(self) -> None:
        """Close the connections."""
        await self.http.aclose()

    async def health(self) -> HealthResponse:
        """Return ``GET /health``."""
        return parse(HealthResponse, await self.http.get("/health"))

    async def search(
        self, query: str, limit: int | None = None
    ) -> SearchResponse:
        """Return ``GET /search``; limit defaults to the server's."""
        response = await self.http.get(
            "/search", params=search_params(query, limit)
        )
        return parse(SearchResponse, response)

    async def document(self, doc_id: int) -> DocumentResponse:
        """Return ``GET /docs/<doc_id>``."""
        response = await self.http.get(f"/docs/{doc_id}")
        return parse(DocumentResponse, response)
