"""The pydantic models of the HTTP contract.

They describe the JSON of the three routes, so the same classes give
the FastAPI server its response schemas and OpenAPI document, and
give ``sift.client`` the parsed answers. The JSON is the one of the
raw server of ``sift.server.raw``, key for key.

>>> HealthResponse(status="ok", docs=8).model_dump_json()
'{"status":"ok","docs":8}'
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from sift.document import Document
from sift.search import Hit, SearchResult
from sift.snippet import render_plain


class HitModel(BaseModel):
    """One ranked document of a search."""

    model_config = ConfigDict(frozen=True)

    doc_id: int
    title: str
    path: str = Field(description="path as the index stores it")
    score: float
    snippet: str = Field(description="plain text, hits in [brackets]")

    @classmethod
    def from_hit(cls, hit: Hit) -> Self:
        """Return the model of a Hit."""
        return cls(
            doc_id=hit.doc_id,
            title=hit.title,
            path=str(hit.path),
            score=hit.score,
            snippet=render_plain(hit.snippet),
        )


class SearchResponse(BaseModel):
    """The answer to ``GET /search``."""

    model_config = ConfigDict(frozen=True)

    query: str
    total: int = Field(description="documents that match the query")
    took_ms: float
    hits: list[HitModel]

    @classmethod
    def from_result(cls, result: SearchResult) -> Self:
        """Return the model of a SearchResult."""
        return cls(
            query=result.query,
            total=result.total,
            took_ms=result.took_ms,
            hits=[HitModel.from_hit(hit) for hit in result.hits],
        )


class DocumentResponse(BaseModel):
    """The answer to ``GET /docs/<id>``."""

    model_config = ConfigDict(frozen=True)

    doc_id: int
    path: str
    title: str
    published: str = Field(description="ISO 8601")
    updated: str | None
    tags: list[str]
    category: str | None
    series: str | None
    body: str

    @classmethod
    def from_document(cls, doc: Document) -> Self:
        """Return the model of a Document."""
        return cls(
            doc_id=doc.doc_id,
            path=str(doc.path),
            title=doc.title,
            published=doc.published.isoformat(),
            updated=doc.updated.isoformat() if doc.updated else None,
            tags=list(doc.tags),
            category=doc.category,
            series=doc.series,
            body=doc.body,
        )


class HealthResponse(BaseModel):
    """The answer to ``GET /health``."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    docs: int = Field(description="documents in the index")


class ErrorResponse(BaseModel):
    """The body of every 4xx and 5xx answer.

    ``query`` and ``position`` are there for a malformed query only.
    """

    error: str
    query: str | None = None
    position: int | None = None
