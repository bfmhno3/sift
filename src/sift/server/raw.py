"""A hand-written HTTP/1.1 server on asyncio streams.

``sift serve --raw`` runs it. It reads the request line and the
headers itself, answers JSON and closes the connection.

The contract
============

Routes (the query string is percent-decoded as UTF-8):

``GET /search?q=<query>[&limit=<n>]``
    The ``sift search --json`` payload for the query. ``q`` is
    required and must not be blank; ``limit`` defaults to
    ``Config.limit`` and follows its range (1 to 100).
``GET /docs/<id>``
    The metadata and the body of one document.
``GET /health``
    ``{"status": "ok", "docs": <n>}``.

Methods: ``GET`` and ``HEAD``. ``HEAD`` runs the same handler and
sends the same status line and headers, ``Content-Length`` included,
and no body. Any other method on a known path is 405 with an
``Allow: GET, HEAD`` header; on an unknown path it is 404.

Statuses: 200 ok; 400 for a request the server cannot parse or a
parameter it rejects; 404 for an unknown path or an unknown document
id; 405 for a method other than GET and HEAD; 500 if the handler
raises; 503 with ``Retry-After: 1`` if the server is full (see
Limits); 504 if a search takes longer than ``SEARCH_TIMEOUT``. A
timeout while reading the head closes the connection with no answer.
The error body is ``{"error": "<message>"}``; a malformed query adds
``"query"`` and ``"position"``.

A request is rejected with 400 if:

* the request line is not ``METHOD SP target SP HTTP/1.0|1.1``, the
  method is not a token or the target is not an absolute path;
* the head is not ASCII, uses a bare CR or LF, has a header line
  without a colon, with a space before the colon or folded, or more
  than 100 headers;
* the head (request line, headers and the blank line) is longer than
  16 KiB, or the connection closes in the middle of it;
* the version is 1.1 and ``Host`` is missing, empty or repeated;
* a query parameter is repeated, is not UTF-8 or has no ``=``;
* ``limit`` is not an integer in range, or ``q`` is missing or blank;
* the query is malformed;
* the id in ``/docs/<id>`` is not 1 or more ASCII digits (leading
  zeros do not count: ``/docs/0001`` is document 1);
* the server is bound to a loopback address and ``Host`` is not
  ``127.0.0.1``, ``localhost`` or ``[::1]``, with or without a
  ``:port``. That stops DNS rebinding: a web page cannot reach the
  server through a name of its own. A server bound to another
  address (``--host 0.0.0.0``) does not check ``Host``.

Every response carries ``Connection: close``: one request per
connection, so a request body is never parsed and cannot be mistaken
for the next request. If the request declares a body
(``Content-Length`` or ``Transfer-Encoding``) or its head was too
large, the server half-closes after the answer and reads and drops
input for up to ``LINGER`` seconds before it closes; closing with
unread input would send a reset that can destroy the answer. One log
line per request goes to the ``sift.server.raw`` logger: peer,
request, status, size, time.

The search runs in the default thread pool: the event loop keeps
answering while a query runs. Searcher is not thread-safe (its LRU
cache is not), so a lock lets one search run at a time. Under the
GIL a query is CPU work and could not overlap with another anyway.

Limits (constants of this module; ``start`` can override them):

* ``MAX_CONNECTIONS`` open connections; the next one is answered 503
  at once and closed.
* ``MAX_PENDING`` searches running or waiting; the next one is 503.
* ``SEARCH_TIMEOUT`` seconds from the moment a search is accepted;
  then the answer is 504. A thread cannot be stopped, so a search
  that already runs finishes; one that waits for the lock or the
  pool is dropped, and so is one whose client has closed its end
  (a client that half-closes before the answer counts as gone). A
  dropped search is logged with status 503.

Security: the server has no authentication and no TLS. By default it
listens on 127.0.0.1; ``start`` logs a WARNING if it listens on any
other address. The JSON of ``/search`` and ``/docs/<id>`` carries the
path of each document as the index stores it, which is an absolute
path if the corpus was indexed with one: that leaks the layout of the
server's disk to every client.

>>> head = b"GET /health HTTP/1.1\\r\\nHost: x\\r\\n\\r\\n"
>>> request = parse_head(head)
>>> request.method, request.path, request.headers["host"]
('GET', '/health', 'x')
"""

import asyncio
import contextlib
import errno
import ipaddress
import json
import logging
import re
import signal
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import formatdate
from http import HTTPStatus
from urllib.parse import parse_qsl

from sift.config import Config
from sift.document import Document
from sift.errors import ConfigError, QuerySyntaxError, SiftError
from sift.search import Searcher, SearchResult
from sift.snippet import render_plain

logger = logging.getLogger("sift.server.raw")

MAX_HEAD = 16 * 1024  # bytes: request line, headers and blank line
MAX_HEADERS = 100
MAX_PARAMS = 20
MAX_ID_DIGITS = 18  # more digits cannot be a doc id: unknown, 404
MAX_LIMIT_DIGITS = 3  # more digits cannot be a valid limit (max 100)
MAX_CONNECTIONS = 256  # open connections; more get 503
MAX_PENDING = 32  # searches running or waiting; more get 503
SEARCH_TIMEOUT = 10.0  # seconds a search may take before 504
READ_TIMEOUT = 10.0  # seconds to receive a complete head
LINGER = 1.0  # seconds to drain input the server will not read
GRACE = 5.0  # seconds a stopping server waits for open requests
METHODS = ("GET", "HEAD")
END_OF_HEAD = b"\r\n\r\n"

_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_TARGET = re.compile(r"/[\x21-\x7e]*")
_VALUE = re.compile(r"[\t\x20-\x7e]*")
LOOPBACK_HOST = re.compile(
    r"(127\.0\.0\.1|localhost|\[::1\])(:[0-9]{1,5})?", re.IGNORECASE
)


class ClientGone(Exception):
    """A search was dropped because nobody waits for its answer."""


def is_loopback(host: str) -> bool:
    """Return True if host names this machine only.

    >>> [is_loopback(h) for h in ("127.0.0.1", "::1", "localhost")]
    [True, True, True]
    >>> [is_loopback(h) for h in ("0.0.0.0", "", "10.0.0.2", "a.org")]
    [False, False, False, False]
    """
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HttpError(Exception):
    """An answer other than 200, raised where the problem is found.

    head_only is True for a HEAD request, whose answer has no body.
    unread is True if input is left that the server will not read.
    headers are added to the response; detail is added to the error
    body.
    """

    def __init__(
        self,
        status: HTTPStatus,
        message: str,
        *,
        head_only: bool = False,
        unread: bool = False,
        headers: tuple[tuple[str, str], ...] = (),
        detail: Mapping[str, object] | None = None,
    ) -> None:
        """Keep the status, the message and the extras."""
        super().__init__(status, message)
        self.status = status
        self.message = message
        self.head_only = head_only
        self.unread = unread
        self.headers = headers
        self.detail = detail or {}

    def payload(self) -> dict[str, object]:
        """Return the JSON body of the error."""
        return {"error": self.message, **self.detail}


@dataclass(frozen=True, slots=True)
class Request:
    """A parsed request: names are lower-cased, params decoded."""

    method: str
    target: str
    path: str
    version: str
    headers: dict[str, str]
    params: dict[str, str]


@dataclass(frozen=True, slots=True)
class Response:
    """A status, a JSON-serializable payload and extra headers."""

    status: HTTPStatus
    payload: object
    headers: tuple[tuple[str, str], ...] = ()

    def encode(self, *, head_only: bool = False) -> tuple[bytes, int]:
        """Return the bytes to send and the length of the body."""
        body = json.dumps(self.payload, ensure_ascii=False).encode()
        lines = [
            f"HTTP/1.1 {self.status.value} {self.status.phrase}",
            f"Date: {formatdate(usegmt=True)}",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body)}",
            "Connection: close",
            *(f"{name}: {value}" for name, value in self.headers),
        ]
        head = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
        return (head if head_only else head + body), len(body)


def _bad(message: str, *, head_only: bool = False) -> HttpError:
    """Return the 400 error for message."""
    return HttpError(HTTPStatus.BAD_REQUEST, message, head_only=head_only)


def limit_from_text(text: str) -> int:
    """Return the hit count that text spells; raise ValueError if bad.

    The message of the ValueError is the text of the 400. Only ASCII
    digits are a number. A number with more than MAX_LIMIT_DIGITS
    digits (after the leading zeros) is out of range whatever it is:
    it is not converted, because int() refuses thousands of digits.
    """
    if not (text.isascii() and text.isdecimal()):
        raise ValueError("limit must be an integer")
    digits = text.lstrip("0") or "0"
    number = int(digits) if len(digits) <= MAX_LIMIT_DIGITS else 10**9
    try:
        return Config.limit.validate(number)
    except ConfigError as error:
        raise ValueError(str(error)) from None


def parse_params(query: str, head_only: bool) -> dict[str, str]:
    """Return the query string as a dict; raise 400 on a bad one."""
    try:
        pairs = parse_qsl(
            query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=MAX_PARAMS,
            errors="strict",
        )
    except ValueError:
        raise _bad("malformed query string", head_only=head_only) from None
    params: dict[str, str] = {}
    for name, value in pairs:
        if name in params:
            raise _bad(f"repeated parameter {name!r}", head_only=head_only)
        params[name] = value
    return params


def _parse_request_line(line: str) -> tuple[str, str, str]:
    """Return method, target and version of a request line."""
    parts = line.split(" ")
    if len(parts) != 3 or not all(parts):
        raise _bad("malformed request line")
    method, target, version = parts
    if not _TOKEN.fullmatch(method):
        raise _bad("malformed request line")
    head_only = method == "HEAD"
    if version not in ("HTTP/1.0", "HTTP/1.1"):
        raise _bad("unsupported HTTP version", head_only=head_only)
    if not _TARGET.fullmatch(target):
        raise _bad(
            "request target must be an absolute path", head_only=head_only
        )
    return method, target, version


def parse_head(head: bytes) -> Request:
    """Parse a request head (up to and with the blank line).

    Raise HttpError(400) if it breaks the rules of the module
    docstring.
    """
    try:
        text = head.decode("ascii")
    except UnicodeDecodeError:
        raise _bad("request head is not ASCII") from None
    lines = text.removesuffix("\r\n\r\n").split("\r\n")
    if any("\r" in line or "\n" in line for line in lines):
        raise _bad("bare CR or LF in the request head")
    method, target, version = _parse_request_line(lines[0])
    head_only = method == "HEAD"
    if len(lines) - 1 > MAX_HEADERS:
        raise _bad("too many headers", head_only=head_only)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        value = value.strip(" \t")
        if not colon or not _TOKEN.fullmatch(name):
            raise _bad("malformed header line", head_only=head_only)
        if not _VALUE.fullmatch(value):
            raise _bad("bad character in a header", head_only=head_only)
        name = name.lower()
        if name == "host" and name in headers:
            raise _bad("repeated Host header", head_only=head_only)
        headers[name] = (
            f"{headers[name]}, {value}" if name in headers else value
        )
    if version == "HTTP/1.1" and not headers.get("host"):
        raise _bad("missing Host header", head_only=head_only)
    path, _, rest = target.partition("#")[0].partition("?")
    return Request(
        method,
        target,
        path,
        version,
        headers,
        parse_params(rest, head_only),
    )


def search_payload(result: SearchResult) -> dict[str, object]:
    """Return the JSON object of ``sift search --json`` for result."""
    return {
        "query": result.query,
        "total": result.total,
        "took_ms": result.took_ms,
        "hits": [
            {
                "doc_id": hit.doc_id,
                "title": hit.title,
                "path": str(hit.path),
                "score": hit.score,
                "snippet": render_plain(hit.snippet),
            }
            for hit in result.hits
        ],
    }


def document_payload(doc: Document) -> dict[str, object]:
    """Return the JSON object of one document."""
    return {
        "doc_id": doc.doc_id,
        "path": str(doc.path),
        "title": doc.title,
        "published": doc.published.isoformat(),
        "updated": doc.updated.isoformat() if doc.updated else None,
        "tags": list(doc.tags),
        "category": doc.category,
        "series": doc.series,
        "body": doc.body,
    }


class RawServer:
    """The routes of the contract over one Searcher and its Config.

    A server keeps no global state: the Searcher, the Config and the
    search lock belong to the instance, so any number of servers can
    run in one process (the tests start one per test, on port 0).
    """

    def __init__(
        self,
        searcher: Searcher,
        config: Config,
        *,
        read_timeout: float = READ_TIMEOUT,
        check_host: bool = False,
        max_connections: int = MAX_CONNECTIONS,
        max_pending: int = MAX_PENDING,
        search_timeout: float = SEARCH_TIMEOUT,
    ) -> None:
        """Serve searcher; config gives the default hit count.

        check_host turns on the Host check of the contract; the
        other keywords override the limits.
        """
        self.searcher = searcher
        self.config = config
        self.read_timeout = read_timeout
        self.check_host = check_host
        self.max_connections = max_connections
        self.max_pending = max_pending
        self.search_timeout = search_timeout
        self._lock = threading.Lock()
        self._connections = 0
        self._pending = 0

    def _search(
        self, query: str, limit: int, gone: Callable[[], bool]
    ) -> SearchResult:
        """Run one search, alone: the Searcher is not thread-safe.

        Runs in a pool thread. gone() is asked once the lock is held;
        if it is true nobody waits for the answer and no work is done.
        """
        with self._lock:
            if gone():
                raise ClientGone
            return self.searcher.search(query, limit)

    def _search_done(self, future: object) -> None:
        """Count a finished (or dropped) search out of the pending."""
        self._pending -= 1

    def _limit(self, params: Mapping[str, str], head_only: bool) -> int:
        """Return the hit count asked for, or the configured one."""
        text = params.get("limit")
        if text is None:
            return self.config.limit
        try:
            return limit_from_text(text)
        except ValueError as error:
            raise _bad(str(error), head_only=head_only) from None

    async def _handle_search(
        self, request: Request, gone: Callable[[], bool]
    ) -> Response:
        """Answer ``/search``."""
        head_only = request.method == "HEAD"
        query = request.params.get("q", "")
        if not query.strip():
            raise _bad("missing query parameter q", head_only=head_only)
        limit = self._limit(request.params, head_only)
        if self._pending >= self.max_pending:
            raise HttpError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "server busy",
                head_only=head_only,
                headers=(("Retry-After", "1"),),
            )
        abandoned = threading.Event()
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            None,
            self._search,
            query,
            limit,
            lambda: abandoned.is_set() or gone(),
        )
        self._pending += 1
        future.add_done_callback(self._search_done)
        try:
            result = await asyncio.wait_for(future, self.search_timeout)
        except TimeoutError:
            raise HttpError(
                HTTPStatus.GATEWAY_TIMEOUT,
                f"search took more than {self.search_timeout:g} s",
                head_only=head_only,
            ) from None
        except ClientGone:
            raise HttpError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "client left before the search ran",
                head_only=head_only,
            ) from None
        except QuerySyntaxError as error:
            raise HttpError(
                HTTPStatus.BAD_REQUEST,
                str(error),
                head_only=head_only,
                detail={"query": error.query, "position": error.position},
            ) from None
        finally:
            abandoned.set()
        return Response(HTTPStatus.OK, search_payload(result))

    def _handle_doc(self, request: Request, text: str) -> Response:
        """Answer ``/docs/<text>``."""
        head_only = request.method == "HEAD"
        if not (text.isascii() and text.isdecimal()):
            raise _bad("bad document id", head_only=head_only)
        doc = None
        digits = text.lstrip("0") or "0"
        if len(digits) <= MAX_ID_DIGITS:
            doc = self.searcher.index.documents.get(int(digits))
        if doc is None:
            raise HttpError(
                HTTPStatus.NOT_FOUND,
                f"no document with id {text}",
                head_only=head_only,
            )
        return Response(HTTPStatus.OK, document_payload(doc))

    async def dispatch(
        self, request: Request, gone: Callable[[], bool] = lambda: False
    ) -> Response:
        """Return the response to request; raise HttpError.

        gone() tells a search whether its client has left.
        """
        head_only = request.method == "HEAD"
        host = request.headers.get("host")
        if (
            self.check_host
            and host is not None
            and not LOOPBACK_HOST.fullmatch(host)
        ):
            raise _bad("Host not allowed", head_only=head_only)
        path = request.path
        known = path in ("/search", "/health") or path.startswith("/docs/")
        if not known:
            raise HttpError(
                HTTPStatus.NOT_FOUND,
                f"no route for {path}",
                head_only=head_only,
            )
        if request.method not in METHODS:
            raise HttpError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                f"method {request.method} not allowed",
                headers=(("Allow", ", ".join(METHODS)),),
            )
        if path == "/search":
            return await self._handle_search(request, gone)
        if path == "/health":
            payload = {"status": "ok", "docs": self.searcher.index.n_docs}
            return Response(HTTPStatus.OK, payload)
        return self._handle_doc(request, path.removeprefix("/docs/"))

    async def _read_head(self, reader: asyncio.StreamReader) -> bytes | None:
        """Read one head; None if the client left without a byte."""
        try:
            async with asyncio.timeout(self.read_timeout):
                return await reader.readuntil(END_OF_HEAD)
        except asyncio.IncompleteReadError as error:
            if not error.partial:
                return None
            raise _bad("incomplete request head") from None
        except asyncio.LimitOverrunError:
            raise HttpError(
                HTTPStatus.BAD_REQUEST,
                "request head too large",
                unread=True,
            ) from None

    async def answer(
        self, reader: asyncio.StreamReader
    ) -> tuple[str, bytes, int, HTTPStatus, bool] | None:
        """Read one request; return what to send and what to log.

        The result is ``(request line, bytes, body size, status,
        unread)``, or None if there is nothing to answer. unread is
        True if the request declared a body or the head was too
        large: input may be left that the server will not read.
        """
        line = "-"
        head_only = False
        unread = False
        try:
            head = await self._read_head(reader)
            if head is None:
                return None
            line = ascii(head.split(b"\r\n", 1)[0][:200].decode("latin-1"))
            request = parse_head(head)
            line = f"{request.method} {request.target}"
            head_only = request.method == "HEAD"
            unread = (
                "content-length" in request.headers
                or "transfer-encoding" in request.headers
            )
            response = await self.dispatch(
                request,
                lambda: reader.at_eof() or reader.exception() is not None,
            )
        except HttpError as error:
            unread = unread or error.unread
            head_only = error.head_only
            response = Response(error.status, error.payload(), error.headers)
        except TimeoutError:
            logger.info("timeout waiting for a request head")
            return None
        except Exception:
            logger.exception("unhandled error in %s", line)
            response = Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "internal server error"},
            )
        wire, size = response.encode(head_only=head_only)
        return line, wire, size, response.status, unread

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Serve one connection: one request, one answer, close."""
        started = time.perf_counter()
        peer = writer.get_extra_info("peername")
        full = self._connections >= self.max_connections
        if not full:
            self._connections += 1
        done: tuple[str, bytes, int, HTTPStatus, bool] | None
        try:
            if full:
                response = Response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": "too many connections"},
                    (("Retry-After", "1"),),
                )
                wire, size = response.encode()
                done = ("-", wire, size, response.status, True)
            else:
                done = await self.answer(reader)
            if done is not None:
                line, wire, size, status, unread = done
                writer.write(wire)
                await writer.drain()
                logger.info(
                    "%s %s %d %dB %.1fms",
                    f"{peer[0]}:{peer[1]}" if peer else "-",
                    line,
                    status.value,
                    size,
                    (time.perf_counter() - started) * 1000,
                )
                if unread:
                    writer.write_eof()
                    await self._discard(reader)
        except OSError as error:
            logger.info("connection lost: %s", error)
        finally:
            if not full:
                self._connections -= 1
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    @staticmethod
    async def _discard(reader: asyncio.StreamReader) -> None:
        """Read and drop input for a moment, so close sends no RST."""
        try:
            async with asyncio.timeout(LINGER):
                while await reader.read(MAX_HEAD):
                    pass
        except TimeoutError, OSError:
            pass


async def start(
    searcher: Searcher,
    config: Config,
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    read_timeout: float = READ_TIMEOUT,
    max_connections: int = MAX_CONNECTIONS,
    max_pending: int = MAX_PENDING,
    search_timeout: float = SEARCH_TIMEOUT,
) -> asyncio.Server:
    """Start listening and return the server (port 0: any free port).

    The Host check is on if host is a loopback address; a WARNING is
    logged if it is not. Raise SiftError if host and port cannot be
    bound, for instance because the port is in use.
    """
    loopback = is_loopback(host)
    app = RawServer(
        searcher,
        config,
        read_timeout=read_timeout,
        check_host=loopback,
        max_connections=max_connections,
        max_pending=max_pending,
        search_timeout=search_timeout,
    )
    try:
        server = await asyncio.start_server(
            app.handle,
            host,
            port,
            limit=MAX_HEAD - len(END_OF_HEAD),
            backlog=max(100, max_connections),
        )
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            reason = "address already in use"
        else:
            reason = error.strerror or str(error)
        raise SiftError(f"cannot listen on {host}:{port}: {reason}") from None
    if not loopback:
        logger.warning(
            "listening on %s: no authentication, and responses carry "
            "document paths; anyone who can connect can read them",
            host or "all addresses",
        )
    return server


def address(server: asyncio.Server) -> tuple[str, int]:
    """Return the host and port a started server listens on."""
    host, port = server.sockets[0].getsockname()[:2]
    return str(host), int(port)


async def serve(
    searcher: Searcher,
    config: Config,
    host: str,
    port: int,
    *,
    announce: Callable[[str], None],
    read_timeout: float = READ_TIMEOUT,
    max_pending: int = MAX_PENDING,
) -> None:
    """Serve until SIGTERM, then stop cleanly.

    announce gets the URL once the socket listens. On SIGTERM the
    server stops accepting, waits up to GRACE seconds for the open
    requests, then drops the rest and returns. Ctrl-C raises
    KeyboardInterrupt out of asyncio.run, as usual.
    """
    server = await start(
        searcher,
        config,
        host,
        port,
        read_timeout=read_timeout,
        max_pending=max_pending,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    bound_host, bound_port = address(server)
    shown = f"[{bound_host}]" if ":" in bound_host else bound_host
    announce(f"listening on http://{shown}:{bound_port}")
    try:
        await stop.wait()
    finally:
        loop.remove_signal_handler(signal.SIGTERM)
        server.close()
        try:
            await asyncio.wait_for(server.wait_closed(), GRACE)
        except TimeoutError:
            server.abort_clients()
