"""Tests for sift.server.app: the FastAPI server.

The app is driven with ``fastapi.testclient.TestClient``, in process
and without sockets. A TestClient runs the lifespan handler only
inside a ``with`` block, so every test uses the ``client`` fixture.
"""

import asyncio
import os
import signal
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from sift.config import Config
from sift.errors import IndexCorruptError, SiftError
from sift.search import Searcher, SearchResult
from sift.server.app import (
    LIMIT_MAX,
    LIMIT_MIN,
    Runtime,
    create_app,
    listen,
    serve,
)
from sift.server.raw import HttpError, RawServer, parse_head

# the target of a request and the status the raw server gives it
SAME_AS_RAW = [
    "/health",
    "/search?q=chain+tool",
    "/search?q=tea&limit=1",
    "/search?q=%22tea+ceremony%22&limit=2",
    "/search?q=a+OR+the",
    "/search?q=caf%C3%A9",
    "/search?q=chain%2A",
    "/docs/2",
    "/docs/0002",
    "/docs/8",
    "/docs/" + "9" * 30,
    "/docs/abc",
    "/docs/-1",
    "/docs/1.5",
    "/search",
    "/search?q=",
    "/search?q=%20+%20",
    "/search?limit=3",
    "/search?q=a&limit=x",
    "/search?q=a&limit=",
    "/search?q=a&limit=-1",
    "/search?q=a&limit=1.5",
    "/search?q=a&limit=1.0",
    "/search?q=a&limit=+1",
    "/search?q=a&limit=1_0",
    "/search?q=a&limit=%EF%BC%91",
    "/search?q=a&limit=0",
    "/search?q=a&limit=101",
    "/search?q=(chain",
    "/search?q=chain+AND",
    "/search?q=%22unclosed",
    "/nope",
    "/docs",
]


def fastapi_app(searcher: Searcher, **options: float | bool) -> FastAPI:
    """Return the app over searcher, with the default Config."""
    return create_app(lambda: nullcontext(searcher), Config(), **options)


@pytest.fixture
def client(searcher: Searcher) -> Iterator[TestClient]:
    """Return a TestClient inside the lifespan of a new app."""
    with TestClient(fastapi_app(searcher)) as running:
        yield running


def raw_answer(
    searcher: Searcher, target: str
) -> tuple[int, dict[str, object]]:
    """Return the status and the JSON the raw server gives to target."""
    head = f"GET {target} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode()
    server = RawServer(searcher, Config())

    async def ask() -> tuple[int, dict[str, object]]:
        try:
            response = await server.dispatch(parse_head(head))
        except HttpError as error:
            return error.status.value, error.payload()
        assert isinstance(response.payload, dict)
        return response.status.value, response.payload

    return asyncio.run(ask())


def fastapi_answer(
    client: TestClient, target: str
) -> tuple[int, dict[str, object]]:
    """Return the status and the JSON the app gives to target."""
    response = client.get(target)
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert isinstance(body, dict)
    return response.status_code, body


def without_time(body: dict[str, object]) -> dict[str, object]:
    """Return body without took_ms, which differs by nature."""
    return {key: value for key, value in body.items() if key != "took_ms"}


# -- same contract as the raw server -----------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "/search?q=chain+tool",
        "/search?q=tea&limit=1",
        "/search?q=river*+OR+bicycle&limit=3",
    ],
)
def test_search_is_the_json_of_the_raw_server(
    searcher: Searcher, client: TestClient, target: str
) -> None:
    status, body = fastapi_answer(client, target)
    raw_status, raw_body = raw_answer(searcher, target)
    assert status == raw_status == 200
    assert body["hits"]
    assert without_time(body) == without_time(raw_body)
    assert isinstance(body["took_ms"], float)


@pytest.mark.parametrize("target", SAME_AS_RAW)
def test_every_answer_is_the_answer_of_the_raw_server(
    searcher: Searcher, client: TestClient, target: str
) -> None:
    status, body = fastapi_answer(client, target)
    raw_status, raw_body = raw_answer(searcher, target)
    assert (status, without_time(body)) == (
        raw_status,
        without_time(raw_body),
    )


def test_search_answers_in_utf8(client: TestClient) -> None:
    response = client.get("/search", params={"q": "café"})
    assert response.status_code == 200
    assert "café".encode() in response.content


def test_search_limit_and_default(client: TestClient) -> None:
    one = client.get("/search?q=a+OR+the&limit=1").json()
    assert len(one["hits"]) == 1
    assert one["total"] > 1
    many = client.get("/search?q=a+OR+the").json()
    assert 1 < len(many["hits"]) <= Config().limit


def test_the_default_limit_is_the_one_of_the_config(
    searcher: Searcher,
) -> None:
    app = create_app(lambda: nullcontext(searcher), Config(limit=2))
    with TestClient(app) as small:
        body = small.get("/search?q=a+OR+the").json()
    assert len(body["hits"]) == 2


def test_syntax_error_has_query_and_position(client: TestClient) -> None:
    response = client.get("/search?q=(chain")
    assert response.status_code == 400
    assert response.json() == {
        "error": "expected ')'",
        "query": "(chain",
        "position": 6,
    }


def test_a_rejected_parameter_is_400_not_422(client: TestClient) -> None:
    for target in ("/search", "/search?q=a&limit=x", "/docs/abc"):
        response = client.get(target)
        assert response.status_code == 400
        assert list(response.json()) == ["error"]


def test_the_limit_range_is_the_one_of_the_config() -> None:
    assert Config.limit.min == LIMIT_MIN
    assert Config.limit.max == LIMIT_MAX


def test_unknown_document_and_route(client: TestClient) -> None:
    assert client.get("/docs/999").json() == {
        "error": "no document with id 999"
    }
    assert client.get("/nope").json() == {"error": "no route for /nope"}


def test_other_methods_are_405(client: TestClient) -> None:
    for method in ("POST", "PUT", "DELETE", "HEAD"):
        response = client.request(method, "/health")
        assert response.status_code == 405
        assert response.headers["allow"] == "GET"
    body = client.post("/search").json()
    assert body == {"error": "method POST not allowed"}
    assert client.post("/nope").status_code == 404


def test_a_crash_is_a_json_500(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(query: str, limit: int = 10) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(searcher, "search", broken)
    app = fastapi_app(searcher)
    with TestClient(app, raise_server_exceptions=False) as running:
        response = running.get("/search?q=tea")
        assert response.status_code == 500
        assert response.json() == {"error": "internal server error"}
        assert running.get("/health").status_code == 200


# -- OpenAPI -----------------------------------------------------------


def test_openapi_lists_the_routes_and_no_422(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    assert list(spec["paths"]) == ["/health", "/search", "/docs/{doc_id}"]
    for path in spec["paths"].values():
        assert "422" not in path["get"]["responses"]
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    params = {
        p["name"]: p for p in spec["paths"]["/search"]["get"]["parameters"]
    }
    assert params["q"]["required"] is True
    assert params["limit"]["required"] is False
    assert params["limit"]["schema"]["minimum"] == LIMIT_MIN
    assert params["limit"]["schema"]["maximum"] == LIMIT_MAX
    assert params["limit"]["schema"]["default"] == Config().limit


def test_swagger_ui_does_not_hide_the_docs_route(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200
    assert client.get("/docs/2").json()["doc_id"] == 2


# -- lifespan ----------------------------------------------------------


def test_the_lifespan_opens_and_closes_one_searcher(
    searcher: Searcher,
) -> None:
    events: list[str] = []

    @contextmanager
    def opened() -> Iterator[Searcher]:
        events.append("open")
        try:
            yield searcher
        finally:
            events.append("close")

    with TestClient(create_app(opened, Config())) as running:
        assert events == ["open"]
        for _ in range(3):
            assert running.get("/health").status_code == 200
        assert events == ["open"]
    assert events == ["open", "close"]


def test_each_app_has_its_own_searcher(searcher: Searcher) -> None:
    other = Searcher(searcher.index, k1=0.0)
    with (
        TestClient(fastapi_app(searcher)) as one,
        TestClient(fastapi_app(other)) as two,
    ):
        a = one.get("/search?q=tea").json()
        b = two.get("/search?q=tea").json()
    assert a["total"] == b["total"]
    assert a["hits"][0]["score"] != b["hits"][0]["score"]


# -- Host --------------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.1:8000", "localhost", "LOCALHOST:80", "[::1]:9"],
)
def test_loopback_hosts_are_accepted(searcher: Searcher, host: str) -> None:
    app = fastapi_app(searcher, check_host=True)
    with TestClient(app) as running:
        assert (
            running.get("/health", headers={"Host": host}).status_code == 200
        )


@pytest.mark.parametrize(
    "host", ["evil.example", "localhost.evil.example", "127.0.0.1.evil", ""]
)
def test_other_hosts_are_400_with_a_loopback_bind(
    searcher: Searcher, host: str
) -> None:
    app = fastapi_app(searcher, check_host=True)
    with TestClient(app) as running:
        response = running.get("/health", headers={"Host": host})
    assert response.status_code == 400
    assert response.json() == {"error": "Host not allowed"}


def test_without_check_host_any_host_is_served(client: TestClient) -> None:
    response = client.get("/health", headers={"Host": "evil.example"})
    assert response.status_code == 200


# -- search limits -----------------------------------------------------


def slow(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch, delay: float
) -> dict[str, int]:
    """Make searcher.search sleep; return counters of how it ran."""
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

    monkeypatch.setattr(searcher, "search", search)
    return stats


def runtime_for(searcher: Searcher, **options: float) -> Runtime:
    """Return a Runtime over searcher with the limits in options."""
    values = {"max_pending": 32, "search_timeout": 10.0} | options
    return Runtime(
        searcher,
        Config(),
        int(values["max_pending"]),
        values["search_timeout"],
    )


def test_searches_run_one_at_a_time_in_threads(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    stats = slow(searcher, monkeypatch, 0.002)
    words = ["chain", "tea", "river", "compiler", "bridges", "gears"]
    expected = {w: searcher.search(w, 10).total for w in words}
    stats["calls"] = 0
    runtime = runtime_for(searcher, max_pending=500)

    async def scenario() -> list[int]:
        jobs = [runtime.search(words[i % 6], 10) for i in range(120)]
        results = await asyncio.gather(*jobs)
        assert [r.query for r in results] == [words[i % 6] for i in range(120)]
        return [r.total for r in results]

    totals = asyncio.run(scenario())
    assert totals == [expected[words[i % 6]] for i in range(120)]
    assert stats["calls"] == 120
    assert stats["peak"] == 1
    assert runtime.pending == 0


def test_the_loop_answers_while_a_search_runs(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow(searcher, monkeypatch, 0.5)
    runtime = runtime_for(searcher)

    async def scenario() -> float:
        task = asyncio.create_task(runtime.search("chain", 10))
        await asyncio.sleep(0.1)  # the search sleeps in a thread now
        started = time.perf_counter()
        await asyncio.sleep(0)
        quick = time.perf_counter() - started
        assert not task.done()
        await task
        return quick

    assert asyncio.run(scenario()) < 0.25


def test_pending_searches_are_capped(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    stats = slow(searcher, monkeypatch, 0.3)
    runtime = runtime_for(searcher, max_pending=2)

    async def scenario() -> list[object]:
        jobs = [runtime.search("chain", 10) for _ in range(5)]
        return await asyncio.gather(*jobs, return_exceptions=True)

    results = asyncio.run(scenario())
    refused = [r for r in results if isinstance(r, HTTPException)]
    assert len(refused) == 3
    assert {r.status_code for r in refused} == {503}
    assert refused[0].headers == {"Retry-After": "1"}
    assert stats["calls"] == 2
    assert runtime.pending == 0


def test_a_search_over_the_deadline_is_504(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow(searcher, monkeypatch, 0.4)
    runtime = runtime_for(searcher, search_timeout=0.1)

    async def scenario() -> HTTPException:
        with pytest.raises(HTTPException) as caught:
            await runtime.search("chain", 10)
        return caught.value

    error = asyncio.run(scenario())
    assert error.status_code == 504
    assert error.detail == "search took more than 0.1 s"
    assert runtime.pending == 0


def test_a_timed_out_search_that_never_started_is_not_run(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    stats = slow(searcher, monkeypatch, 0.5)
    runtime = runtime_for(searcher, search_timeout=0.1)

    async def scenario() -> None:
        first = asyncio.create_task(runtime.search("chain", 10))
        await asyncio.sleep(0.02)
        second = asyncio.create_task(runtime.search("tea", 10))
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(r, HTTPException) for r in results)
        # the first thread finishes; the second gets the lock and must
        # see that nobody waits for it
        await asyncio.sleep(0.6)

    asyncio.run(scenario())
    assert stats["calls"] == 1


def test_too_many_requests_over_http_get_503(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow(searcher, monkeypatch, 0.3)
    app = fastapi_app(searcher, max_pending=1)
    answers: list[int] = []

    def ask(running: TestClient) -> None:
        answers.append(running.get("/search?q=chain").status_code)

    with TestClient(app) as running:
        threads = [
            threading.Thread(target=ask, args=(running,)) for _ in "abc"
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert sorted(answers) == [200, 503, 503]


# -- serve -------------------------------------------------------------


def test_the_listening_socket_is_tcp_so_that_asyncio_sets_nodelay() -> None:
    with listen("127.0.0.1", 0, 10) as sock:
        assert sock.proto == socket.IPPROTO_TCP
        client = socket.create_connection(sock.getsockname())
        with client, sock.accept()[0] as accepted:
            # asyncio tests proto == IPPROTO_TCP before TCP_NODELAY
            assert accepted.proto == socket.IPPROTO_TCP


def test_serve_stops_cleanly_on_sigterm(searcher: Searcher) -> None:
    announced: list[str] = []

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            serve(
                lambda: nullcontext(searcher),
                Config(),
                "127.0.0.1",
                0,
                announce=announced.append,
                quiet=True,
            )
        )
        while not announced and not task.done():
            await asyncio.sleep(0.01)
        port = int(announced[0].rsplit(":", 1)[1])
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Connection: close\r\n\r\n"
        )
        await writer.drain()
        assert b"200 OK" in await reader.read()
        writer.close()
        loop.call_soon(os.kill, os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(task, 10)
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", port)

    before = signal.getsignal(signal.SIGTERM)
    asyncio.run(scenario())
    assert announced[0].startswith("listening on http://127.0.0.1:")
    assert signal.getsignal(signal.SIGTERM) == before


def test_serve_on_a_busy_port_is_a_clear_error(searcher: Searcher) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(SiftError) as caught:
            asyncio.run(
                serve(
                    lambda: nullcontext(searcher),
                    Config(),
                    "127.0.0.1",
                    port,
                    announce=print,
                )
            )
    assert str(caught.value) == (
        f"cannot listen on 127.0.0.1:{port}: address already in use"
    )


def test_serve_with_an_unknown_host_is_a_clear_error(
    searcher: Searcher,
) -> None:
    with pytest.raises(SiftError, match="cannot listen on no.such.host"):
        asyncio.run(
            serve(
                lambda: nullcontext(searcher),
                Config(),
                "no.such.host.invalid",
                0,
                announce=print,
            )
        )


def test_serve_raises_the_error_of_the_lifespan(searcher: Searcher) -> None:
    @contextmanager
    def corrupt() -> Iterator[Searcher]:
        raise IndexCorruptError("segment is damaged")
        yield searcher  # pragma: no cover

    announced: list[str] = []
    with pytest.raises(IndexCorruptError, match="segment is damaged"):
        asyncio.run(
            serve(
                corrupt,
                Config(),
                "127.0.0.1",
                0,
                announce=announced.append,
                quiet=True,
            )
        )
    assert announced == []
