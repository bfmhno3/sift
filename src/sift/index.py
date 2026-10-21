"""Inverted index, version 1: plain dicts of dicts."""

from collections import Counter


def build_index(docs: dict[int, list[str]]) -> dict[str, dict[int, int]]:
    """Return term -> {doc_id: term frequency} for tokenized documents."""
    index: dict[str, dict[int, int]] = {}
    for doc_id, tokens in docs.items():
        for term, tf in Counter(tokens).items():
            index.setdefault(term, {})[doc_id] = tf
    return index
