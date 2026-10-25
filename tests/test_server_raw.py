"""Tests for sift.server.raw: parsing, routes, concurrency."""

import asyncio
import json
import logging
import os
import signal
import socket
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus

import pytest

from sift.config import Config
from sift.errors import SiftError
from sift.index import InvertedIndex
from sift.search import Searcher, SearchResult
from sift.server.raw import (
    MAX_HEAD,
    HttpError,
    address,
    document_payload,
    is_loopback,
    parse_head,
    serve,
    start,
)

GOOD = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"


@dataclass
class Answer:
    """One parsed response."""

    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> dict[str, object]:
        """Return the body as a JSON object."""
        data = json.loads(self.body)
        assert isinstance(data, dict)
        return data


def parse_answer(raw: bytes) -> Answer:
    """Split the bytes of a response into status, headers and body."""
    head, sep, body = raw.partition(b"\r\n\r\n")
    assert sep, raw
    first, *lines = head.decode("ascii").split("\r\n")
    version, code, _ = first.split(" ", 2)
    assert version == "HTTP/1.1"
    headers = dict(line.split(": ", 1) for line in lines)
    return Answer(int(code), headers, body)


async def talk(port: int, request: bytes) -> Answer:
    """Send the bytes of a request, read until the server closes."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(request)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    return parse_answer(raw)


async def get(port: int, target: str, method: str = "GET") -> Answer:
    """Send ``method target`` with a Host header and read the answer."""
    request = f"{method} {target} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
    return await talk(port, request.encode())


@asynccontextmanager
async def running(searcher: Searcher, **options: float) -> AsyncIterator[int]:
    """Serve searcher on a free port; yield the port."""
    server = await start(searcher, Config(), "127.0.0.1", 0, **options)
    try:
        yield address(server)[1]
    finally:
        server.close()
        await server.wait_closed()


def with_server(
    searcher: Searcher,
    check: Callable[[int], Awaitable[None]],
    **options: float,
) -> None:
    """Start a server on a free port and run ``check(port)``."""

    async def scenario() -> None:
        async with running(searcher, **options) as port:
            await check(port)

    asyncio.run(scenario())


def head_error(raw: bytes) -> HttpError:
    """Return the HttpError that parse_head raises for raw."""
    with pytest.raises(HttpError) as caught:
        parse_head(raw)
    assert caught.value.status == HTTPStatus.BAD_REQUEST
    return caught.value


# -- parse_head --------------------------------------------------------


def test_parse_a_plain_request() -> None:
    request = parse_head(
        b"GET /search?q=a+b%C3%A9&limit=3#frag HTTP/1.1\r\n"
        b"Host: example.org\r\nX-Dup: 1\r\nx-dup:  2 \r\n\r\n"
    )
    assert request.method == "GET"
    assert request.path == "/search"
    assert request.target == "/search?q=a+b%C3%A9&limit=3#frag"
    assert request.version == "HTTP/1.1"
    assert request.params == {"q": "a b\u00e9", "limit": "3"}
    assert request.headers == {"host": "example.org", "x-dup": "1, 2"}


def test_http_1_0_needs_no_host() -> None:
    request = parse_head(b"GET /health HTTP/1.0\r\n\r\n")
    assert request.headers == {}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"\r\n\r\n", "malformed request line"),
        (b"BAD\r\n\r\n", "malformed request line"),
        (b"GET /\r\n\r\n", "malformed request line"),
        (b"GET  / HTTP/1.1\r\nHost: x\r\n\r\n", "malformed request line"),
        (b"GET / HTTP/1.1 x\r\nHost: x\r\n\r\n", "malformed request line"),
        (b"G@T / HTTP/1.1\r\nHost: x\r\n\r\n", "malformed request line"),
        (b"GET / HTTP/2\r\nHost: x\r\n\r\n", "unsupported HTTP version"),
        (b"GET / http/1.1\r\nHost: x\r\n\r\n", "unsupported HTTP version"),
        (
            b"GET http://x/ HTTP/1.1\r\nHost: x\r\n\r\n",
            "request target must be an absolute path",
        ),
        (
            b"OPTIONS * HTTP/1.1\r\nHost: x\r\n\r\n",
            "request target must be an absolute path",
        ),
        (b"GET /x HTTP/1.1\r\n\r\n", "missing Host header"),
        (b"GET /x HTTP/1.1\r\nHost:\r\n\r\n", "missing Host header"),
        (
            b"GET /x HTTP/1.1\r\nHost: a\r\nhost: b\r\n\r\n",
            "repeated Host header",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost: x\r\nnocolon\r\n\r\n",
            "malformed header line",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost : x\r\n\r\n",
            "malformed header line",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost: x\r\n folded\r\n\r\n",
            "malformed header line",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost: x\r\nX: a\x01b\r\n\r\n",
            "bad character in a header",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost: x\nX: y\r\n\r\n",
            "bare CR or LF in the request head",
        ),
        (
            b"GET /x HTTP/1.1\r\nHost: x\rX: y\r\n\r\n",
            "bare CR or LF in the request head",
        ),
        (
            "GET /x HTTP/1.1\r\nHost: caf\u00e9\r\n\r\n".encode(),
            "request head is not ASCII",
        ),
        (
            b"GET /x?q=\xff HTTP/1.1\r\nHost: x\r\n\r\n",
            "request head is not ASCII",
        ),
        (
            b"GET /x?q=%ff HTTP/1.1\r\nHost: x\r\n\r\n",
            "malformed query string",
        ),
        (
            b"GET /x?q HTTP/1.1\r\nHost: x\r\n\r\n",
            "malformed query string",
        ),
        (
            b"GET /x?q=1&q=2 HTTP/1.1\r\nHost: x\r\n\r\n",
            "repeated parameter 'q'",
        ),
    ],
)
def test_parse_rejects_with_400(raw: bytes, message: str) -> None:
    assert head_error(raw).message == message


def test_parse_rejects_too_many_params() -> None:
    query = "&".join(f"p{i}=1" for i in range(21))
    raw = f"GET /x?{query} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
    assert head_error(raw).message == "malformed query string"


def test_parse_rejects_more_than_100_headers() -> None:
    many = b"".join(b"H%d: v\r\n" % i for i in range(101))
    raw = b"GET /x HTTP/1.1\r\nHost: x\r\n" + many + b"\r\n"
    assert head_error(raw).message == "too many headers"
    few = b"".join(b"H%d: v\r\n" % i for i in range(99))
    parse_head(b"GET /x HTTP/1.1\r\nHost: x\r\n" + few + b"\r\n")


def test_errors_after_a_head_request_line_have_no_body() -> None:
    assert head_error(b"HEAD /x HTTP/1.1\r\n\r\n").head_only
    assert head_error(b"HEAD /x HTTP/9\r\n\r\n").head_only
    assert not head_error(b"GET /x HTTP/1.1\r\n\r\n").head_only
    assert not head_error(b"HEAD\r\n\r\n").head_only


# -- routes ------------------------------------------------------------


def test_health(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        answer = await talk(port, GOOD)
        assert answer.status == 200
        assert answer.json() == {"status": "ok", "docs": 8}
        assert answer.headers["Connection"] == "close"
        assert answer.headers["Content-Type"] == (
            "application/json; charset=utf-8"
        )
        assert int(answer.headers["Content-Length"]) == len(answer.body)
        assert answer.headers["Date"].endswith(" GMT")

    with_server(searcher, check)


def test_search_matches_the_searcher(searcher: Searcher) -> None:
    expected = searcher.search("chain tool", 10)
    assert expected.total == 1

    async def check(port: int) -> None:
        answer = await get(port, "/search?q=chain+tool")
        assert answer.status == 200
        body = answer.json()
        assert body["total"] == expected.total
        assert body["query"] == "chain tool"
        hits = body["hits"]
        assert isinstance(hits, list)
        assert [hit["doc_id"] for hit in hits] == [
            hit.doc_id for hit in expected.hits
        ]
        assert "[chain]" in hits[0]["snippet"].lower()
        assert hits[0]["title"] == expected.hits[0].title
        assert hits[0]["score"] == expected.hits[0].score

    with_server(searcher, check)


def test_search_limit_and_default(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        one = (await get(port, "/search?q=a+OR+the&limit=1")).json()
        assert len(one["hits"]) == 1
        assert one["total"] > 1
        many = (await get(port, "/search?q=a+OR+the")).json()
        assert 1 < len(many["hits"]) <= Config().limit

    with_server(searcher, check)


def test_search_answers_in_utf8(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        answer = await get(port, "/search?q=caf%C3%A9")
        assert answer.status == 200
        assert "café".encode() in answer.body
        assert int(answer.headers["Content-Length"]) == len(answer.body)

    with_server(searcher, check)


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("/search", "missing query parameter q"),
        ("/search?q=", "missing query parameter q"),
        ("/search?q=%20+%20", "missing query parameter q"),
        ("/search?limit=3", "missing query parameter q"),
        ("/search?q=a&limit=x", "limit must be an integer"),
        ("/search?q=a&limit=", "limit must be an integer"),
        ("/search?q=a&limit=-1", "limit must be an integer"),
        ("/search?q=a&limit=1.5", "limit must be an integer"),
        ("/search?q=a&limit=0", "must be an integer between 1 and 100"),
        ("/search?q=a&limit=101", "must be an integer between 1 and 100"),
        ("/search?q=a&limit=%EF%BC%91", "limit must be an integer"),
    ],
)
def test_search_parameter_errors(
    searcher: Searcher, target: str, message: str
) -> None:
    async def check(port: int) -> None:
        answer = await get(port, target)
        assert answer.status == 400
        error = answer.json()["error"]
        assert isinstance(error, str)
        assert message in error

    with_server(searcher, check)


def test_search_syntax_error_reports_the_position(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        answer = await get(port, "/search?q=(chain")
        assert answer.status == 400
        body = answer.json()
        assert body["query"] == "(chain"
        assert body["position"] == 6
        assert "error" in body

    with_server(searcher, check)


def test_docs_returns_one_document(searcher: Searcher) -> None:
    doc = searcher.index.documents[2]

    async def check(port: int) -> None:
        answer = await get(port, "/docs/2")
        assert answer.status == 200
        assert answer.json() == json.loads(
            json.dumps(document_payload(doc), ensure_ascii=False)
        )
        assert answer.json()["title"] == doc.title
        assert (await get(port, "/docs/002")).json()["doc_id"] == 2

    with_server(searcher, check)


@pytest.mark.parametrize(
    "target",
    ["/docs/8", "/docs/999", "/docs/" + "9" * 18, "/docs/" + "9" * 5000],
)
def test_unknown_document_is_404(searcher: Searcher, target: str) -> None:
    async def check(port: int) -> None:
        answer = await get(port, target)
        assert answer.status == 404
        assert "no document" in str(answer.json()["error"])

    with_server(searcher, check)


@pytest.mark.parametrize(
    "target",
    ["/docs/", "/docs/abc", "/docs/-1", "/docs/1.5", "/docs/1/2", "/docs/%31"],
)
def test_bad_document_id_is_400(searcher: Searcher, target: str) -> None:
    async def check(port: int) -> None:
        answer = await get(port, target)
        assert answer.status == 400
        assert answer.json() == {"error": "bad document id"}

    with_server(searcher, check)


@pytest.mark.parametrize(
    "target", ["/", "/nope", "/docs", "/health/", "/search/", "/Health"]
)
def test_unknown_path_is_404(searcher: Searcher, target: str) -> None:
    async def check(port: int) -> None:
        for method in ("GET", "HEAD", "POST"):
            answer = await get(port, target, method)
            assert answer.status == 404
            assert answer.headers["Content-Type"].startswith("application")
        assert "no route" in str((await get(port, target)).json()["error"])

    with_server(searcher, check)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "FOO"])
@pytest.mark.parametrize("target", ["/search?q=a", "/docs/0", "/health"])
def test_other_methods_are_405(
    searcher: Searcher, method: str, target: str
) -> None:
    async def check(port: int) -> None:
        answer = await get(port, target, method)
        assert answer.status == 405
        assert answer.headers["Allow"] == "GET, HEAD"
        assert answer.json()["error"] == f"method {method} not allowed"

    with_server(searcher, check)


def test_method_names_are_case_sensitive(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        assert (await get(port, "/health", "get")).status == 405

    with_server(searcher, check)


@pytest.mark.parametrize(
    "target", ["/health", "/search?q=chain", "/docs/1", "/docs/99", "/nope"]
)
def test_head_is_get_without_a_body(searcher: Searcher, target: str) -> None:
    async def check(port: int) -> None:
        full = await get(port, target)
        head = await get(port, target, "HEAD")
        assert head.status == full.status
        assert head.body == b""
        assert int(head.headers["Content-Length"]) > 0
        assert head.headers["Content-Type"] == full.headers["Content-Type"]
        assert head.headers["Connection"] == "close"
        if "took_ms" not in full.body.decode():
            assert (
                head.headers["Content-Length"]
                == (full.headers["Content-Length"])
            )

    with_server(searcher, check)


def test_head_with_a_bad_head_has_no_body(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        answer = await talk(port, b"HEAD /health HTTP/1.1\r\n\r\n")
        assert answer.status == 400
        assert answer.body == b""
        assert int(answer.headers["Content-Length"]) > 0
        answer = await talk(
            port, b"HEAD /search?q HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        )
        assert answer.status == 400
        assert answer.body == b""

    with_server(searcher, check)


# -- the wire ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"BAD\r\n\r\n",
        b"GET /health\r\n\r\n",
        b"GET /health HTTP/1.1\r\n\r\n",
        b"GET /health HTTP/3\r\nHost: 127.0.0.1\r\n\r\n",
        b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03\r\n\r\n",
    ],
)
def test_malformed_requests_get_400_with_a_body(
    searcher: Searcher, raw: bytes
) -> None:
    async def check(port: int) -> None:
        answer = await talk(port, raw)
        assert answer.status == 400
        assert "error" in answer.json()
        assert answer.headers["Connection"] == "close"

    with_server(searcher, check)


def test_a_huge_head_gets_400_and_the_client_can_read_it(
    searcher: Searcher,
) -> None:
    async def check(port: int) -> None:
        big = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nX: " + b"a" * (
            8 * MAX_HEAD
        )
        answer = await talk(port, big + b"\r\n\r\n")
        assert answer.status == 400
        assert answer.json() == {"error": "request head too large"}
        assert (await talk(port, GOOD)).status == 200

    with_server(searcher, check)


def test_a_head_just_under_the_limit_is_served(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        prefix = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nX: "
        room = MAX_HEAD - len(prefix) - len(b"\r\n\r\n")
        assert (
            await talk(port, prefix + b"a" * room + b"\r\n\r\n")
        ).status == 200
        over = await talk(port, prefix + b"a" * (room + 1) + b"\r\n\r\n")
        assert over.status == 400

    with_server(searcher, check)


def test_a_head_cut_short_gets_400(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHo")
        writer.write_eof()
        answer = parse_answer(await reader.read())
        assert answer.status == 400
        assert answer.json() == {"error": "incomplete request head"}
        writer.close()

    with_server(searcher, check)


def test_a_silent_client_is_dropped_and_not_logged(
    searcher: Searcher, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sift.server.raw")

    async def check(port: int) -> None:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write_eof()  # leaves without a byte
        assert await reader.read() == b""
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        started = time.perf_counter()
        assert await reader.read() == b""  # read_timeout expires
        assert 0.1 < time.perf_counter() - started < 2
        writer.close()
        assert (await talk(port, GOOD)).status == 200

    with_server(searcher, check, read_timeout=0.2)
    lines = [r.getMessage() for r in caplog.records if "GET" in r.getMessage()]
    assert len(lines) == 1


def test_a_request_body_is_ignored(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        raw = (
            b"POST /search HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: 5\r\n\r\nhello"
        )
        assert (await talk(port, raw)).status == 405
        raw = (
            b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: 5\r\n\r\nhello"
        )
        assert (await talk(port, raw)).status == 200

    with_server(searcher, check)


def test_http_1_0_clients_are_answered(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        answer = await talk(port, b"GET /health HTTP/1.0\r\n\r\n")
        assert answer.status == 200
        assert answer.headers["Connection"] == "close"

    with_server(searcher, check)


def test_one_log_line_per_request(
    searcher: Searcher, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sift.server.raw")

    async def check(port: int) -> None:
        await get(port, "/health")
        await get(port, "/search?q=chain")
        await get(port, "/nope", "POST")
        await talk(port, b"BAD\r\n\r\n")

    with_server(searcher, check)
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 4
    assert all(line.startswith("127.0.0.1:") for line in lines)
    assert " GET /health 200 27B " in lines[0]
    assert " GET /search?q=chain 200 " in lines[1]
    assert " POST /nope 404 " in lines[2]
    assert " 'BAD' 400 " in lines[3]
    assert all(line.endswith("ms") for line in lines)


def test_the_log_line_escapes_what_the_client_sent(
    searcher: Searcher, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sift.server.raw")

    async def check(port: int) -> None:
        await talk(port, b"GET /\x1b[31mred\r\n\r\n")

    with_server(searcher, check)
    (line,) = [r.getMessage() for r in caplog.records]
    assert "\x1b" not in line
    assert "\\x1b" in line


def test_an_unexpected_error_is_a_500_and_the_server_lives(
    searcher: Searcher,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def boom(query: str, limit: int = 10) -> SearchResult:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(searcher, "search", boom)

    async def check(port: int) -> None:
        answer = await get(port, "/search?q=chain")
        assert answer.status == 500
        assert answer.json() == {"error": "internal server error"}
        assert b"secret" not in answer.body
        assert (await talk(port, GOOD)).status == 200

    with_server(searcher, check)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


# -- start, address, serve ---------------------------------------------


def test_port_zero_picks_a_free_port(searcher: Searcher) -> None:
    async def scenario() -> None:
        first = await start(searcher, Config(), "127.0.0.1", 0)
        second = await start(searcher, Config(), "127.0.0.1", 0)
        try:
            assert address(first)[1] != address(second)[1]
            assert address(first)[1] > 0
        finally:
            first.close()
            second.close()
            await asyncio.gather(first.wait_closed(), second.wait_closed())

    asyncio.run(scenario())


def test_port_in_use_is_a_clear_error(searcher: Searcher) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(SiftError) as caught:
            asyncio.run(start(searcher, Config(), "127.0.0.1", port))
    assert str(caught.value) == (
        f"cannot listen on 127.0.0.1:{port}: address already in use"
    )


def test_an_unknown_host_is_a_clear_error(searcher: Searcher) -> None:
    with pytest.raises(
        SiftError, match="cannot listen on no.such.host.invalid"
    ):
        asyncio.run(start(searcher, Config(), "no.such.host.invalid", 0))


def test_two_servers_do_not_share_state(
    searcher: Searcher, mini_index: InvertedIndex
) -> None:
    other = Searcher(mini_index, k1=0.0)

    async def scenario() -> None:
        async with running(searcher) as one, running(other) as two:
            a = (await get(one, "/search?q=chain")).json()
            b = (await get(two, "/search?q=chain")).json()
            assert a["total"] == b["total"]

    asyncio.run(scenario())


def test_serve_stops_cleanly_on_sigterm(searcher: Searcher) -> None:
    announced: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            serve(
                searcher,
                Config(),
                "127.0.0.1",
                0,
                announce=announced.append,
            )
        )
        while not announced:
            await asyncio.sleep(0.01)
        port = int(announced[0].rsplit(":", 1)[1])
        assert (await get(port, "/health")).status == 200
        loop.call_soon(os.kill, os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, 5)
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", port)

    asyncio.run(scenario())
    assert announced[0].startswith("listening on http://127.0.0.1:")


# -- concurrency -------------------------------------------------------


def slow_search(
    searcher: Searcher, delay: float
) -> tuple[Callable[[str, int], SearchResult], dict[str, int]]:
    """Return a search that sleeps, and counters of how it ran."""
    real = searcher.search
    stats = {"running": 0, "peak": 0, "calls": 0}
    guard = threading.Lock()

    def search(query: str, limit: int = 10) -> SearchResult:
        with guard:
            stats["running"] += 1
            stats["calls"] += 1
            stats["peak"] = max(stats["peak"], stats["running"])
        try:
            time.sleep(delay)
            return real(query, limit)
        finally:
            with guard:
                stats["running"] -= 1

    return search, stats


def test_the_loop_answers_while_a_search_runs(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = slow_search(searcher, 0.5)
    monkeypatch.setattr(searcher, "search", search)

    async def check(port: int) -> None:
        slow = asyncio.create_task(get(port, "/search?q=chain"))
        await asyncio.sleep(0.1)  # the search is now asleep in a thread
        started = time.perf_counter()
        health = await talk(port, GOOD)
        quick = time.perf_counter() - started
        assert health.status == 200
        assert quick < 0.25
        assert not slow.done()
        assert (await slow).status == 200

    with_server(searcher, check)


def test_many_clients_get_the_right_answers_one_search_at_a_time(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, stats = slow_search(searcher, 0.002)
    monkeypatch.setattr(searcher, "search", search)
    words = ["chain", "tea", "river", "compiler", "bridges", "gears"]
    expected = {w: searcher.search(w, 10).total for w in words}
    stats["calls"] = 0

    async def check(port: int) -> None:
        jobs = [get(port, f"/search?q={words[i % 6]}") for i in range(120)]
        answers = await asyncio.gather(*jobs)
        for i, answer in enumerate(answers):
            assert answer.status == 200
            body = answer.json()
            assert body["query"] == words[i % 6]
            assert body["total"] == expected[words[i % 6]]

    with_server(searcher, check, max_pending=200)
    assert stats["calls"] == 120
    assert stats["peak"] == 1


# -- bodies, Host, ids, limits ------------------------------------------


def test_a_large_unread_body_does_not_eat_the_answer(
    searcher: Searcher,
) -> None:
    async def check(port: int) -> None:
        post = (
            b"POST /search HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: 1000000\r\n\r\n" + b"x" * 1_000_000
        )
        answer = await talk(port, post)
        assert answer.status == 405
        big = 5_000_000
        get_ = (
            b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Content-Length: %d\r\n\r\n" % big + b"x" * big
        )
        answer = await talk(port, get_)
        assert answer.status == 200
        chunked = (
            b"POST /health HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n" + b"x" * 2_000_000
        )
        assert (await talk(port, chunked)).status == 405

    with_server(searcher, check)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.0.0.1:8000",
        "localhost",
        "LOCALHOST:80",
        "[::1]",
        "[::1]:65535",
    ],
)
def test_loopback_hosts_are_accepted(searcher: Searcher, host: str) -> None:
    async def check(port: int) -> None:
        raw = f"GET /health HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
        assert (await talk(port, raw)).status == 200

    with_server(searcher, check)


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:80",
        "127.0.0.1.evil.example",
        "localhost.evil.example",
        "127.0.0.2",
        "localhost:",
        "localhost:123456",
        "0.0.0.0",
        "[::2]",
    ],
)
def test_other_hosts_are_400_on_a_loopback_bind(
    searcher: Searcher, host: str
) -> None:
    async def check(port: int) -> None:
        for method in ("GET", "HEAD", "POST"):
            raw = f"{method} /nope HTTP/1.1\r\nHost: {host}\r\n\r\n"
            answer = await talk(port, raw.encode())
            assert answer.status == 400
            assert (answer.body == b"") == (method == "HEAD")
        error = (await get(port, "/health")).status
        assert error == 200  # the helper sends Host: 127.0.0.1

    with_server(searcher, check)

    # the answer says why
    async def why(port: int) -> None:
        raw = f"GET /health HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
        assert (await talk(port, raw)).json() == {"error": "Host not allowed"}

    with_server(searcher, why)


def test_http_1_0_without_host_is_served_on_a_loopback_bind(
    searcher: Searcher,
) -> None:
    async def check(port: int) -> None:
        answer = await talk(port, b"GET /health HTTP/1.0\r\n\r\n")
        assert answer.status == 200

    with_server(searcher, check)


def test_a_wildcard_bind_skips_the_host_check_and_warns(
    searcher: Searcher, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sift.server.raw")

    async def scenario() -> None:
        server = await start(searcher, Config(), "0.0.0.0", 0)
        try:
            port = address(server)[1]
            raw = b"GET /health HTTP/1.1\r\nHost: anything\r\n\r\n"
            assert (await talk(port, raw)).status == 200
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "no authentication" in warnings[0].getMessage()


def test_a_loopback_bind_does_not_warn(
    searcher: Searcher, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sift.server.raw")
    with_server(searcher, lambda port: asyncio.sleep(0))
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_is_loopback() -> None:
    assert is_loopback("127.0.0.1")
    assert is_loopback("127.1.2.3")
    assert is_loopback("::1")
    assert is_loopback("localhost")
    assert not is_loopback("")
    assert not is_loopback("0.0.0.0")
    assert not is_loopback("::")
    assert not is_loopback("example.org")


@pytest.mark.parametrize(
    ("target", "doc_id"),
    [
        ("/docs/000000000000000001", 1),
        ("/docs/" + "0" * 40 + "1", 1),
        ("/docs/" + "0" * 5000 + "3", 3),
        ("/docs/" + "0" * 30, 0),
    ],
)
def test_zero_padded_ids_count_by_value(
    searcher: Searcher, target: str, doc_id: int
) -> None:
    async def check(port: int) -> None:
        answer = await get(port, target)
        assert answer.status == 200
        assert answer.json()["doc_id"] == doc_id

    with_server(searcher, check)


def test_a_long_id_by_value_is_404(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        for text in ("1" + "0" * 18, "0" * 30 + "9" * 19):
            assert (await get(port, "/docs/" + text)).status == 404

    with_server(searcher, check)


# -- limits ---------------------------------------------------------------


def test_pending_searches_are_capped(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, stats = slow_search(searcher, 0.3)
    monkeypatch.setattr(searcher, "search", search)

    async def check(port: int) -> None:
        answers = await asyncio.gather(
            *[get(port, "/search?q=chain") for _ in range(8)]
        )
        codes = sorted(a.status for a in answers)
        assert codes == [200] * 2 + [503] * 6
        busy = next(a for a in answers if a.status == 503)
        assert busy.headers["Retry-After"] == "1"
        assert busy.json() == {"error": "server busy"}
        # the burst is over: a normal request works again
        assert (await get(port, "/search?q=chain")).status == 200
        assert (await talk(port, GOOD)).status == 200

    with_server(searcher, check, max_pending=2)
    assert stats["calls"] == 3


def test_a_search_over_the_deadline_is_504(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = slow_search(searcher, 0.5)
    monkeypatch.setattr(searcher, "search", search)

    async def check(port: int) -> None:
        answer = await get(port, "/search?q=chain")
        assert answer.status == 504
        assert "took more than 0.1 s" in str(answer.json()["error"])
        assert (await talk(port, GOOD)).status == 200
        head = await get(port, "/search?q=chain", "HEAD")
        assert head.status == 504
        assert head.body == b""

    with_server(searcher, check, search_timeout=0.1)


def test_searches_of_clients_that_left_are_skipped(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, stats = slow_search(searcher, 0.4)
    monkeypatch.setattr(searcher, "search", search)

    async def check(port: int) -> None:
        first = asyncio.create_task(get(port, "/search?q=chain"))
        await asyncio.sleep(0.1)  # the first search holds the lock
        for _ in range(5):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(
                b"GET /search?q=tea HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
            )
            await writer.drain()
            writer.close()
        assert (await first).status == 200
        await asyncio.sleep(0.5)
        assert (await get(port, "/search?q=river")).status == 200

    with_server(searcher, check)
    assert stats["calls"] == 2  # the first, and the last; not the five


def test_a_timed_out_search_that_never_started_is_not_run(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    search, stats = slow_search(searcher, 0.15)
    monkeypatch.setattr(searcher, "search", search)

    async def check(port: int) -> None:
        answers = await asyncio.gather(
            *[get(port, "/search?q=chain") for _ in range(4)]
        )
        assert sorted(a.status for a in answers) == [200, 504, 504, 504]
        await asyncio.sleep(0.8)

    with_server(searcher, check, search_timeout=0.2)
    # the second was running at 0.2 s and finishes; the others, whose
    # clients got 504 by then, never run
    assert stats["calls"] == 2


def test_extra_connections_get_503(searcher: Searcher) -> None:
    async def check(port: int) -> None:
        idle = [
            await asyncio.open_connection("127.0.0.1", port) for _ in range(2)
        ]
        await asyncio.sleep(0.05)
        answer = await talk(port, GOOD)
        assert answer.status == 503
        assert answer.headers["Retry-After"] == "1"
        assert answer.json() == {"error": "too many connections"}
        for _, writer in idle:
            writer.close()
        await asyncio.sleep(0.1)
        assert (await talk(port, GOOD)).status == 200

    with_server(searcher, check, max_connections=2)
