"""Tests for sift.client without a network: httpx.MockTransport."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from sift.client import ApiError, AsyncSiftClient, SiftClient
from sift.errors import QuerySyntaxError, SiftError

SEARCH = {
    "query": "tea",
    "total": 1,
    "took_ms": 0.5,
    "hits": [
        {
            "doc_id": 4,
            "title": "Tea",
            "path": "tea.md",
            "score": 1.5,
            "snippet": "a [tea] break",
        }
    ],
}


def mock(
    status: int = 200,
    body: object = None,
    *,
    content: bytes | None = None,
    seen: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    """Return a transport that answers every request the same way."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if content is not None:
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


def test_search_builds_the_url_and_parses_the_body() -> None:
    seen: list[httpx.Request] = []
    with SiftClient(
        "http://sift.test", transport=mock(body=SEARCH, seen=seen)
    ) as c:
        result = c.search("tea & coffee", limit=3)
    assert (
        str(seen[0].url) == "http://sift.test/search?q=tea+%26+coffee&limit=3"
    )
    assert result.hits[0].doc_id == 4
    assert result.hits[0].snippet == "a [tea] break"


def test_search_without_limit_sends_none() -> None:
    seen: list[httpx.Request] = []
    with SiftClient(
        "http://sift.test", transport=mock(body=SEARCH, seen=seen)
    ) as c:
        c.search("tea")
    assert seen[0].url.params.get("limit") is None


def test_models_are_frozen() -> None:
    with SiftClient("http://sift.test", transport=mock(body=SEARCH)) as c:
        result = c.search("tea")
    assert isinstance(result.took_ms, float)
    assert result.model_config["frozen"] is True


def test_a_syntax_error_comes_back_as_the_library_exception() -> None:
    body = {"error": "expected ')'", "query": "(tea", "position": 4}
    with (
        SiftClient("http://sift.test", transport=mock(400, body)) as c,
        pytest.raises(QuerySyntaxError) as caught,
    ):
        c.search("(tea")
    assert caught.value.render() == "expected ')'\n  (tea\n      ^"


@pytest.mark.parametrize("status", [400, 404, 503, 504])
def test_other_errors_carry_status_and_message(status: int) -> None:
    transport = mock(status, {"error": "nope"})
    with (
        SiftClient("http://sift.test", transport=transport) as c,
        pytest.raises(ApiError) as caught,
    ):
        c.document(1)
    assert caught.value.status == status
    assert str(caught.value) == f"{status}: nope"
    assert isinstance(caught.value, SiftError)


def test_a_body_that_is_not_an_error_falls_back_to_the_reason() -> None:
    transport = mock(503, content=b"Service Unavailable")
    with (
        SiftClient("http://sift.test", transport=transport) as c,
        pytest.raises(ApiError) as caught,
    ):
        c.health()
    assert str(caught.value) == "503: Service Unavailable"


def test_a_200_with_a_wrong_body_is_a_validation_error() -> None:
    transport = mock(body={"x": 1})
    with (
        SiftClient("http://sift.test", transport=transport) as c,
        pytest.raises(ValidationError),
    ):
        c.health()


def test_the_timeout_applies_to_every_phase() -> None:
    with SiftClient("http://sift.test", timeout=2.5, transport=mock()) as c:
        assert c.http.timeout == httpx.Timeout(2.5)


def test_the_async_client_does_the_same() -> None:
    seen: list[httpx.Request] = []

    async def scenario() -> None:
        health = {"status": "ok", "docs": 3}
        async with AsyncSiftClient(
            "http://sift.test", transport=mock(body=health, seen=seen)
        ) as c:
            assert (await c.health()).docs == 3
        body = {"error": "expected ')'", "query": "(", "position": 1}
        async with AsyncSiftClient(
            "http://sift.test", transport=mock(400, body)
        ) as c:
            with pytest.raises(QuerySyntaxError):
                await c.search("(")
        async with AsyncSiftClient(
            "http://sift.test", transport=mock(404, {"error": "x"})
        ) as c:
            with pytest.raises(ApiError):
                await c.document(1)

    asyncio.run(scenario())
    assert [r.url.path for r in seen] == ["/health"]


def test_json_dump_of_a_model_is_the_wire_json() -> None:
    with SiftClient("http://sift.test", transport=mock(body=SEARCH)) as c:
        result = c.search("tea")
    assert json.loads(result.model_dump_json()) == SEARCH
