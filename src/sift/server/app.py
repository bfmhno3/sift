"""The FastAPI server: the contract of ``sift.server.raw`` on uvicorn.

``sift serve`` runs it; ``sift serve --raw`` runs the hand-written
server of chapter 17. The routes, the statuses and the JSON are the
ones documented in ``sift.server.raw``; the models of the JSON are in
``sift.server.models``. ``create_app`` builds the application, and
``serve`` runs it on uvicorn.

Where it differs from the raw server
====================================

* ``/docs/<id>`` is a route of Sift, so the Swagger UI and the
  OpenAPI document live under ``/api`` (``/api/docs`` and
  ``/api/openapi.json``). The raw server has neither.
* Only ``GET`` is routed: ``HEAD`` is 405 with ``Allow: GET``.
* HTTP/1.1 connections are kept alive (uvicorn closes an idle one
  after 5 s); the raw server answers once and closes.
* The request head is parsed by h11, not by ``sift.server.raw``:
  malformed heads get uvicorn's plain-text 400, and a repeated query
  parameter is not an error (the last one wins).
* The cap on open connections (``MAX_CONNECTIONS``) is uvicorn's
  ``limit_concurrency``: the 503 it sends has a plain-text body.
* A search whose client has left is not skipped: the search cap and
  the timeout are the same, but nobody checks the connection.

The Host check and the warning for a bind to another address are the
raw server's: a loopback bind accepts only the loopback names. The
400 for a rejected ``q``, ``limit`` or document id has the text
of the raw server; the validators of the parameters see to that.

Searches run in a worker thread (``anyio.to_thread``): a search is
CPU work and would stop the event loop. One lock lets one search run
at a time, because the LRU cache of a Searcher is not thread-safe.
Under the GIL two searches could not overlap anyway. The cheap
routes (``/health``, ``/docs/<id>``) run on the loop.

The application keeps no global state. ``create_app`` takes a function
that opens the Searcher; the ``lifespan`` handler calls it when the
server starts and closes it when the server stops, so the index is
mapped once for the life of the process.
"""

import asyncio
import contextlib
import errno
import logging
import signal
import socket
import threading
from collections.abc import (
    AsyncGenerator,
    Callable,
    Generator,
    Mapping,
)
from contextlib import (
    AbstractContextManager,
    asynccontextmanager,
    contextmanager,
)
from dataclasses import dataclass, field
from typing import Annotated

import anyio
import anyio.to_thread
import uvicorn
from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BeforeValidator, Field
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from sift import __version__
from sift.config import Config
from sift.errors import ConfigError, QuerySyntaxError, SiftError
from sift.search import Searcher, SearchResult
from sift.server.models import (
    DocumentResponse,
    ErrorResponse,
    HealthResponse,
    SearchResponse,
)
from sift.server.raw import (
    GRACE,
    LOOPBACK_HOST,
    MAX_CONNECTIONS,
    MAX_ID_DIGITS,
    MAX_PENDING,
    SEARCH_TIMEOUT,
    is_loopback,
)

logger = logging.getLogger("sift.server.app")

type SearcherSource = Callable[[], AbstractContextManager[Searcher]]

LIMIT_MIN = 1  # the range of Config.limit, for the OpenAPI document
LIMIT_MAX = 100


class Abandoned(Exception):
    """A search was dropped before it ran: nobody awaits its answer."""


def not_blank(text: str) -> str:
    """Return text; raise ValueError (so a 400) if it is blank."""
    if not text.strip():
        raise ValueError("missing query parameter q")
    return text


def parse_limit(value: object) -> int:
    """Return the hit count in value, by the rules of Config.limit.

    A query parameter arrives as str, the default as int. Only ASCII
    digits are a number in a str: pydantic itself would also take
    ``" 5 "``, ``"1_0"`` and ``"1.0"``. Raise ValueError, which
    pydantic turns into an error of the field.
    """
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        number = int(value)
    elif isinstance(value, int) and not isinstance(value, bool):
        number = value
    else:
        raise ValueError("limit must be an integer")
    try:
        return Config.limit.validate(number)
    except ConfigError as error:
        raise ValueError(str(error)) from None


QueryText = Annotated[
    str,
    AfterValidator(not_blank),
    Query(description="the query, in the Sift query language"),
]
# The order matters: pydantic puts a constraint on the schema built so
# far, and after BeforeValidator that schema is the validator, which
# does not know "ge" (the OpenAPI document would say "ge", not
# "minimum"). So Field(ge, le) goes first.
Limit = Annotated[
    int,
    Field(ge=LIMIT_MIN, le=LIMIT_MAX),
    BeforeValidator(parse_limit),
    Query(description="most hits to return (default: [search] limit)"),
]
DocId = Annotated[
    str,
    Path(pattern=r"^[0-9]+$", description="document id, ASCII digits"),
]


@dataclass(eq=False)
class Runtime:
    """What the routes share: the Searcher, the limits, the lock.

    One Runtime lives from the start of the server to its stop and is
    only used by the routes of the application that made it.
    """

    searcher: Searcher
    config: Config
    max_pending: int
    search_timeout: float
    lock: threading.Lock = field(default_factory=threading.Lock)
    pending: int = 0  # searches running or waiting; loop thread only

    def _search(
        self, query: str, limit: int, abandoned: threading.Event
    ) -> SearchResult:
        """Run one search, alone, in a worker thread.

        If the caller stopped waiting while this thread waited for the
        lock, nothing is run.
        """
        with self.lock:
            if abandoned.is_set():
                raise Abandoned
            return self.searcher.search(query, limit)

    async def search(self, query: str, limit: int) -> SearchResult:
        """Search in a worker thread; 503 if full, 504 if too slow.

        The caller is the loop thread, which owns ``pending``. A
        thread cannot be stopped: a search that already runs finishes
        and its answer is dropped.
        """
        if self.pending >= self.max_pending:
            raise HTTPException(
                503, "server busy", headers={"Retry-After": "1"}
            )
        abandoned = threading.Event()
        self.pending += 1
        try:
            with anyio.fail_after(self.search_timeout):
                return await anyio.to_thread.run_sync(
                    self._search,
                    query,
                    limit,
                    abandoned,
                    abandon_on_cancel=True,
                )
        except TimeoutError:
            raise HTTPException(
                504, f"search took more than {self.search_timeout:g} s"
            ) from None
        finally:
            abandoned.set()
            self.pending -= 1


def get_runtime(request: Request) -> Runtime:
    """Return the Runtime that the lifespan handler made.

    This is a dependency: FastAPI calls it for every route that
    declares ``Annotated[Runtime, Depends(get_runtime)]``.
    """
    runtime = request.app.state.runtime
    if not isinstance(runtime, Runtime):
        raise RuntimeError("the lifespan handler did not run")
    return runtime


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


def error_response(
    status: int,
    message: str,
    headers: Mapping[str, str] | None = None,
    *,
    query: str | None = None,
    position: int | None = None,
) -> JSONResponse:
    """Return the JSON error of the contract.

    The body is ``{"error": message}``; a malformed query adds
    ``query`` and ``position``.
    """
    body = ErrorResponse(error=message, query=query, position=position)
    return JSONResponse(
        body.model_dump(exclude_none=True), status, headers=headers
    )


def validation_message(error: RequestValidationError) -> str:
    """Return the text of the first problem in a validation error.

    It is the text of the raw server where that has one: a missing
    or blank ``q``, a ``limit`` that is not a number or out of range,
    a document id that is not digits.
    """
    for problem in error.errors():
        place = ".".join(str(part) for part in problem["loc"][1:])
        kind = str(problem["type"])
        if place == "doc_id":
            return "bad document id"
        if kind == "missing":
            return f"missing query parameter {place}"
        if kind == "value_error":
            return str(problem["ctx"]["error"])
        return f"{place}: {problem['msg']}"
    return "invalid request"


class HostCheck:
    """Answer 400 to a request whose Host is not a loopback name.

    It stops DNS rebinding, like the raw server: a web page cannot
    reach a server on 127.0.0.1 through a name of its own. A request
    without a Host header passes (HTTP/1.0).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap app."""
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Pass the request on, or answer 400."""
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == b"host" and not LOOPBACK_HOST.fullmatch(
                    value.decode("latin-1")
                ):
                    response = error_response(400, "Host not allowed")
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# "4XX" is there to keep FastAPI from adding its 422 to the document:
# every rejected request is a 400 with the body of ErrorResponse.
ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "bad parameter or query"},
    "4XX": {"model": ErrorResponse, "description": "any other error"},
    503: {"model": ErrorResponse, "description": "server busy"},
    504: {"model": ErrorResponse, "description": "search too slow"},
}


async def syntax_error(request: Request, exc: Exception) -> JSONResponse:
    """Map a malformed query to 400 with its position."""
    if not isinstance(exc, QuerySyntaxError):
        raise exc
    return error_response(
        400, str(exc), query=exc.query, position=exc.position
    )


async def invalid_request(request: Request, exc: Exception) -> JSONResponse:
    """Map a rejected parameter to 400 (FastAPI says 422)."""
    if not isinstance(exc, RequestValidationError):
        raise exc
    return error_response(400, validation_message(exc))


async def http_error(request: Request, exc: Exception) -> JSONResponse:
    """Give the errors of the routing the shape of the contract."""
    if not isinstance(exc, HTTPException):
        raise exc
    message = exc.detail
    if exc.status_code == 404 and message == "Not Found":
        message = f"no route for {request.url.path}"
    elif exc.status_code == 405:
        message = f"method {request.method} not allowed"
    return error_response(exc.status_code, message, exc.headers)


async def crashed(request: Request, exc: Exception) -> JSONResponse:
    """Answer an unexpected error with a JSON 500.

    Starlette sends this answer and then raises the exception again,
    so that uvicorn logs the traceback.
    """
    return error_response(500, "internal server error")


async def health(runtime: RuntimeDep) -> HealthResponse:
    """Return the document count of the index."""
    return HealthResponse(status="ok", docs=runtime.searcher.index.n_docs)


async def document(doc_id: DocId, runtime: RuntimeDep) -> DocumentResponse:
    """Return the metadata and the body of one document.

    The id counts by value: `0001` is document 1.
    """
    digits = doc_id.lstrip("0") or "0"
    doc = None
    if len(digits) <= MAX_ID_DIGITS:
        doc = runtime.searcher.index.documents.get(int(digits))
    if doc is None:
        raise HTTPException(404, f"no document with id {doc_id}")
    return DocumentResponse.from_document(doc)


def create_app(
    open_searcher: SearcherSource,
    config: Config,
    *,
    check_host: bool = False,
    max_pending: int = MAX_PENDING,
    search_timeout: float = SEARCH_TIMEOUT,
) -> FastAPI:
    """Return the application over the Searcher open_searcher opens.

    open_searcher is called with no arguments when the server starts
    (the lifespan handler enters the context manager it returns) and
    left when the server stops. config gives the default hit count.
    check_host turns on the Host check; max_pending and
    search_timeout are the limits of the raw server.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """Open the Searcher for the life of the server."""
        with open_searcher() as searcher:
            app.state.runtime = Runtime(
                searcher, config, max_pending, search_timeout
            )
            yield

    async def search(
        q: QueryText, runtime: RuntimeDep, limit: Limit = config.limit
    ) -> SearchResponse:
        """Return the best documents for the query q.

        A malformed query is 400 with `query` and `position`.
        """
        result = await runtime.search(q, limit)
        return SearchResponse.from_result(result)

    app = FastAPI(
        title="Sift",
        summary="Full-text search over the Markdown posts of a blog.",
        description=(
            "No authentication and no TLS: bind to a loopback address. "
            "The `path` of a document is the one the index stores."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    if check_host:
        app.add_middleware(HostCheck)
    app.add_exception_handler(QuerySyntaxError, syntax_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, crashed)
    app.add_api_route(
        "/health",
        health,
        response_model=HealthResponse,
        summary="Is the server up, and how big is the index",
    )
    app.add_api_route(
        "/search",
        search,
        response_model=SearchResponse,
        responses=ERRORS,
        summary="Search the index",
    )
    app.add_api_route(
        "/docs/{doc_id}",
        document,
        response_model=DocumentResponse,
        responses={
            400: ERRORS[400],
            404: {"model": ErrorResponse},
            "4XX": ERRORS["4XX"],
        },
        summary="One document",
    )
    return app


def listen(host: str, port: int, backlog: int) -> socket.socket:
    """Bind and listen; raise SiftError if that is not possible.

    uvicorn's own bind would log the error and exit 3, so the socket
    is made here and handed to uvicorn. It is made with the TCP
    protocol number, not 0 as ``socket.create_server`` does:
    asyncio sets TCP_NODELAY only on sockets whose ``proto`` is TCP,
    and an accepted socket inherits the ``proto`` of the listening
    one. With 0, Nagle's algorithm stays on and every answer on a
    kept-alive connection waits 40 ms for a delayed ACK.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
    except OSError as error:
        sock.close()
        if error.errno == errno.EADDRINUSE:
            reason = "address already in use"
        else:
            reason = error.strerror or str(error)
        raise SiftError(f"cannot listen on {host}:{port}: {reason}") from None
    return sock


@contextmanager
def noting(
    open_searcher: SearcherSource, failures: list[SiftError]
) -> Generator[Searcher]:
    """Open the Searcher; keep a SiftError that opening raises.

    uvicorn only logs an error of the lifespan handler and stops.
    ``serve`` raises the one kept here, so that a corrupt index exits
    1 with its message, as in the raw server.
    """
    try:
        with open_searcher() as searcher:
            yield searcher
    except SiftError as error:
        failures.append(error)
        raise


def _use_sift_handlers(quiet: bool) -> None:
    """Send the logs of uvicorn through the handler of ``sift``.

    uvicorn's own configuration is off (log_config=None), so its
    loggers would have no handler. The access log is one line per
    request, like the raw server's; ``quiet`` turns it off.
    """
    handlers = logging.getLogger("sift").handlers
    for name in ("uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers[:] = handlers
        log.propagate = False
    error = logging.getLogger("uvicorn.error")
    error.setLevel(logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    access.setLevel(logging.WARNING if quiet else logging.INFO)


async def run_server(server: uvicorn.Server, sock: socket.socket) -> None:
    """Run server on sock until it stops.

    When the lifespan handler fails, uvicorn calls ``sys.exit(3)``.
    asyncio lets a SystemExit out of a task and stops the whole loop,
    so it is caught here and ``serve`` looks at ``server.started``.
    """
    with contextlib.suppress(SystemExit):
        await server.serve([sock])


async def serve(
    open_searcher: SearcherSource,
    config: Config,
    host: str,
    port: int,
    *,
    announce: Callable[[str], None],
    max_pending: int = MAX_PENDING,
    quiet: bool = False,
) -> None:
    """Serve until SIGTERM, then stop cleanly.

    announce gets ``listening on <url>`` once the socket listens and
    the lifespan handler has opened the Searcher. Raise SiftError if
    host and port cannot be bound or the Searcher cannot be opened.
    On SIGTERM uvicorn stops accepting, waits up to GRACE seconds for
    the open requests and returns: after that this function returns.
    (uvicorn raises the signal again once it is done; the handler
    installed here swallows SIGTERM, so the exit status is 0. Ctrl-C
    is raised again as KeyboardInterrupt, as with the raw server.)
    """
    loopback = is_loopback(host)
    failures: list[SiftError] = []
    app = create_app(
        lambda: noting(open_searcher, failures),
        config,
        check_host=loopback,
        max_pending=max_pending,
    )
    sock = listen(host, port, backlog=max(100, MAX_CONNECTIONS))
    if not loopback:
        logger.warning(
            "listening on %s: no authentication, and responses carry "
            "document paths; anyone who can connect can read them",
            host or "all addresses",
        )
    _use_sift_handlers(quiet)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_config=None,
            access_log=not quiet,
            server_header=False,
            proxy_headers=False,
            ws="none",
            limit_concurrency=MAX_CONNECTIONS,
            timeout_graceful_shutdown=int(GRACE),
        )
    )
    on_main = threading.current_thread() is threading.main_thread()
    before = signal.signal(signal.SIGTERM, signal.SIG_IGN) if on_main else None
    try:
        task = asyncio.create_task(run_server(server, sock))
        while not server.started and not task.done():
            await asyncio.sleep(0.01)
        if server.started:
            bound_host, bound_port = sock.getsockname()[:2]
            shown = f"[{bound_host}]" if ":" in bound_host else bound_host
            announce(f"listening on http://{shown}:{bound_port}")
        await task
    finally:
        sock.close()
        if before is not None:
            signal.signal(signal.SIGTERM, before)
    if failures:
        raise failures[0]
    if not server.started:
        raise SiftError("the server did not start, see the log")
