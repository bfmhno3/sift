"""Ask the type checker what it infers: reveal_type notes.

At runtime reveal_type prints the type of the value to stderr and
returns it; mypy and pyright print the static type instead.
"""

from pathlib import Path
from typing import reveal_type

from legacy.scores import normalize

from sift.cache import LRUCache
from sift.index import Posting
from sift.scoring import top_k
from sift.search import SearchResult


def first_word(text: str) -> str | None:
    """Return the first word of text, or None for an empty text."""
    words = text.split()
    return words[0] if words else None


def main() -> None:
    """Reveal the inferred types of literals, calls and sift names."""
    count = 3
    ratio = count / 2
    names = ["a", "b"]
    mixed = [1, "x"]
    table = {"a": 1, "b": 2.5}
    squares = {n: n * n for n in range(3)}
    pair = (1, "x")
    reveal_type(count)
    reveal_type(ratio)
    reveal_type(names)
    reveal_type(mixed)
    reveal_type(table)
    reveal_type(squares)
    reveal_type(pair)
    reveal_type(first_word("sift search"))
    reveal_type(Path("corpus") / "posts")
    reveal_type(top_k({1: 0.5}, 1))
    reveal_type(Posting(1, (0, 3)).tf)
    result = SearchResult("sift", 0, 0.0, [])
    reveal_type(result.hits)
    cache = LRUCache[str, int](2)
    reveal_type(cache)
    reveal_type(cache.get("a"))
    reveal_type(cache.hit_rate)
    reveal_type(normalize({1: 2.0}))


if __name__ == "__main__":
    main()
