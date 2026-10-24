"""TypedDict, Required/NotRequired, Literal and Final."""

import json
from typing import Final, Literal, NotRequired, Required, TypedDict

MAX_HITS: Final = 10
DEFAULT_MODE: Final[str] = "and"

type Mode = Literal["and", "or"]


class HitDict(TypedDict):
    """A hit as it travels in JSON: every key is required."""

    doc_id: int
    title: str
    score: float


class SearchRequest(TypedDict, total=False):
    """A request where only ``query`` is required."""

    query: Required[str]
    limit: int
    mode: Mode
    tag: NotRequired[str]


def run(request: SearchRequest) -> str:
    """Describe the request with its defaults filled in."""
    limit = request.get("limit", MAX_HITS)
    mode = request.get("mode", "and")
    return f"{request['query']!r} limit={limit} mode={mode}"


def set_mode(mode: Mode) -> Mode:
    """Return mode; only the two literal strings are accepted."""
    return mode


def main() -> None:
    """Build TypedDicts, which are plain dicts at runtime."""
    hit: HitDict = {"doc_id": 1, "title": "tea", "score": 1.5}
    print(json.dumps(hit), type(hit).__name__)
    print(run({"query": "rust"}))
    print(run({"query": "rust", "limit": 3, "mode": "or", "tag": "Rust"}))
    print(set_mode("or"), DEFAULT_MODE, MAX_HITS)
    print(sorted(SearchRequest.__required_keys__))
    print(sorted(SearchRequest.__optional_keys__))


if __name__ == "__main__":
    main()
