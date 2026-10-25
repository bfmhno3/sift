"""The raw server on a real port, queried with the httpx clients.

``test_server_raw.py`` tests the protocol of the raw server with
hand-written requests. These tests ask the questions of a program:
the server runs on an ephemeral port in a thread of its own, and
``AsyncSiftClient`` and ``SiftClient`` talk to it as any other
client would.
"""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

from sift.client import ApiError, AsyncSiftClient, SiftClient
from sift.config import Config
from sift.errors import QuerySyntaxError
from sift.search import Searcher, SearchResult
from sift.server.raw import address, start


@dataclass(frozen=True)
class Running:
    """A raw server on a port, started by the ``raw_server`` fixture."""

    url: str
    searcher: Searcher


@pytest.fixture
def raw_server(
    searcher: Searcher, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Running]:
    """Serve searcher with the raw server on a free port.

    The server has an event loop in a thread of its own, so a test
    can use a blocking client or its own loop. Its request log is off:
    the server thread logs a line after the client has its answer, and
    that can be after pytest has closed its capture of the test.
    """
    monkeypatch.setattr(logging.getLogger("sift.server.raw"), "disabled", True)
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    stop = asyncio.Event()
    urls: list[str] = []

    async def serve_until_stopped() -> None:
        # 50 searches at once must not meet the default cap of 32
        server = await start(
            searcher, Config(), "127.0.0.1", 0, max_pending=64
        )
        host, port = address(server)
        urls.append(f"http://{host}:{port}")
        ready.set()
        await stop.wait()
        server.close()
        await server.wait_closed()

    thread = threading.Thread(
        target=loop.run_until_complete, args=(serve_until_stopped(),)
    )
    thread.start()
    assert ready.wait(10)
    try:
        yield Running(urls[0], searcher)
    finally:
        loop.call_soon_threadsafe(stop.set)
        thread.join(10)
        loop.close()


def test_async_client_health_and_search(raw_server: Running) -> None:
    expected = raw_server.searcher.search("chain tool", 10)

    async def scenario() -> None:
        async with AsyncSiftClient(raw_server.url) as client:
            health = await client.health()
            assert (health.status, health.docs) == ("ok", 8)
            result = await client.search("chain tool")
            assert result.query == "chain tool"
            assert result.total == expected.total == 1
            assert [h.doc_id for h in result.hits] == [
                h.doc_id for h in expected.hits
            ]
            assert "[chain]" in result.hits[0].snippet.lower()

    asyncio.run(scenario())


def test_async_client_limit_and_document(raw_server: Running) -> None:
    doc = raw_server.searcher.index.documents[2]

    async def scenario() -> None:
        async with AsyncSiftClient(raw_server.url) as client:
            one = await client.search("a OR the", limit=1)
            assert len(one.hits) == 1
            assert one.total > 1
            got = await client.document(2)
            assert (got.doc_id, got.title) == (2, doc.title)
            assert got.body == doc.body
            assert got.published == doc.published.isoformat()

    asyncio.run(scenario())


def test_async_client_errors(raw_server: Running) -> None:
    async def scenario() -> None:
        async with AsyncSiftClient(raw_server.url) as client:
            with pytest.raises(QuerySyntaxError) as syntax:
                await client.search("(chain")
            assert (syntax.value.query, syntax.value.position) == ("(chain", 6)
            with pytest.raises(ApiError, match="no document with id 99") as e:
                await client.document(99)
            assert e.value.status == 404
            with pytest.raises(ApiError) as bad:
                await client.search("a", limit=0)
            assert bad.value.status == 400
            assert "between 1 and 100" in bad.value.message

    asyncio.run(scenario())


def test_fifty_requests_share_one_client(raw_server: Running) -> None:
    async def scenario() -> list[int]:
        async with AsyncSiftClient(raw_server.url) as client:
            results = await asyncio.gather(
                *(client.search(w, limit=1) for w in ["tea", "river"] * 25)
            )
        return [r.total for r in results]

    totals = asyncio.run(scenario())
    assert len(totals) == 50
    assert totals[0] == raw_server.searcher.search("tea", 1).total
    assert totals[1] == raw_server.searcher.search("river", 1).total


def test_sync_client_against_the_same_server(raw_server: Running) -> None:
    with SiftClient(raw_server.url) as client:
        assert client.health().docs == 8
        assert client.search("tea", limit=1).hits
        assert client.document(0).doc_id == 0
        with pytest.raises(QuerySyntaxError):
            client.search("tea AND")


def test_a_slow_search_is_a_read_timeout(
    raw_server: Running, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = raw_server.searcher.search

    def slow(query: str, limit: int = 10) -> SearchResult:
        time.sleep(0.5)
        return real(query, limit)

    monkeypatch.setattr(raw_server.searcher, "search", slow)
    with SiftClient(raw_server.url, timeout=0.1) as client:
        assert client.health().docs == 8
        with pytest.raises(httpx.ReadTimeout):
            client.search("tea")
        # the pool is intact: the next request works
        assert client.health().docs == 8


def test_a_closed_port_is_a_connect_error() -> None:
    with (
        SiftClient("http://127.0.0.1:1") as client,
        pytest.raises(httpx.ConnectError),
    ):
        client.health()
