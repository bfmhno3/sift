"""Inverted index, version 1: plain dicts of dicts."""

from collections import Counter
from collections.abc import Iterable


def build_index(
    docs: Iterable[tuple[int, Iterable[str]]],
) -> dict[str, dict[int, int]]:
    """Return term -> {doc_id: term frequency}.

    docs is consumed once, a document at a time: each item is a
    ``(doc_id, terms)`` pair and the terms may be a generator.
    """
    index: dict[str, dict[int, int]] = {}
    for doc_id, tokens in docs:
        for term, tf in Counter(tokens).items():
            index.setdefault(term, {})[doc_id] = tf
    return index
