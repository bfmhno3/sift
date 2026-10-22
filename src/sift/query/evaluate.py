"""Evaluate a query tree against an index: postings in, postings out."""

from collections.abc import Mapping, Sequence
from typing import assert_never

from sift.analysis import Pipeline, build_pipeline
from sift.index import InvertedIndex, Posting, PostingList
from sift.query.ast import And, Field, Node, Not, Or, Phrase, Prefix, Term


def phrase_postings(
    lookup: Mapping[str, PostingList], terms: Sequence[str]
) -> PostingList:
    """Return the documents where terms occur at consecutive positions.

    The posting of a match keeps the positions where the phrase
    starts, so its tf counts phrase occurrences. A single term is
    just its own posting list. Unlike ``&``, which merges the
    positions of both operands, this keeps each term's positions
    apart and shifts them: term k must sit at start + k.
    """
    if not terms:
        return PostingList()
    lists = [lookup.get(term, PostingList()) for term in terms]
    if len(lists) == 1:
        return lists[0]
    # Drive from the shortest list, probe the others by doc_id.
    driver = min(range(len(lists)), key=lambda k: len(lists[k]))
    others = [
        {p.doc_id: frozenset(p.positions) for p in plist} for plist in lists
    ]
    found: list[Posting] = []
    for posting in lists[driver]:
        doc_id = posting.doc_id
        if any(doc_id not in positions for positions in others):
            continue
        starts = [
            start
            for start in (pos - driver for pos in posting.positions)
            if start >= 0
            and all(start + k in others[k][doc_id] for k in range(len(lists)))
        ]
        if starts:
            found.append(Posting(doc_id, tuple(starts)))
    return PostingList(found)


def _analyzed(pipeline: Pipeline, words: Sequence[str]) -> list[str]:
    """Return the index terms of words, in order."""
    return [term for word in words for term in pipeline.terms(word)]


def _universe(index: InvertedIndex) -> PostingList:
    """Return every document, with empty positions."""
    return PostingList(Posting(doc_id, ()) for doc_id in index.documents)


def _metadata_match(
    name: str, value: str, index: InvertedIndex
) -> PostingList:
    """Return documents whose tag, category or series equals value.

    The comparison is exact and case-insensitive, after collapsing
    runs of whitespace; it is a scan over the documents.
    """
    wanted = " ".join(value.split()).casefold()
    found = []
    for doc_id, doc in index.documents.items():
        match name:
            case "tag":
                values = doc.tags
            case "category":
                values = (doc.category or "",)
            case "series":
                values = (doc.series or "",)
            case _:
                raise ValueError(f"unknown field: {name!r}")
        if any(" ".join(v.split()).casefold() == wanted for v in values):
            found.append(Posting(doc_id, ()))
    return PostingList(found)


def _field(
    name: str, value: Node, index: InvertedIndex, pipeline: Pipeline
) -> PostingList:
    """Evaluate ``name:value``."""
    match name, value:
        case "title", Term(text):
            terms = pipeline.terms(text)
            return phrase_postings(index.title_index, terms)
        case "title", Phrase(words):
            terms = _analyzed(pipeline, words)
            return phrase_postings(index.title_index, terms)
        case _, Term(text):
            return _metadata_match(name, text, index)
        case _, Phrase(words):
            return _metadata_match(name, " ".join(words), index)
        case _:
            raise ValueError(f"bad field value: {value!r}")


def _prefix(
    text: str, index: InvertedIndex, pipeline: Pipeline
) -> PostingList:
    """Evaluate ``text*``: the last token is a prefix of index terms."""
    terms = pipeline.terms(text)
    if not terms:
        return PostingList()
    *head, last = terms
    out = PostingList()
    for term in index.terms_with_prefix(last):
        out = out | phrase_postings(index, [*head, term])
    return out


def evaluate(
    node: Node, index: InvertedIndex, pipeline: Pipeline | None = None
) -> PostingList:
    """Return the documents of index that match node.

    Words are analyzed with pipeline, which must be the one that
    built the index (default: build_pipeline()). A word that gives
    several tokens is a phrase of them; one that gives none matches
    nothing. A NOT is the universe minus its operand, but ``x AND
    NOT y`` is computed as ``x - y`` without building the universe.
    """
    pipeline = pipeline or build_pipeline()
    match node:
        case Term(text):
            return phrase_postings(index, pipeline.terms(text))
        case Prefix(text):
            return _prefix(text, index, pipeline)
        case Phrase(words):
            return phrase_postings(index, _analyzed(pipeline, words))
        case Field(name, value):
            return _field(name, value, index, pipeline)
        case And(left, Not(operand)) | And(Not(operand), left):
            return evaluate(left, index, pipeline) - evaluate(
                operand, index, pipeline
            )
        case And(left, right):
            return evaluate(left, index, pipeline) & evaluate(
                right, index, pipeline
            )
        case Or(left, right):
            return evaluate(left, index, pipeline) | evaluate(
                right, index, pipeline
            )
        case Not(operand):
            return _universe(index) - evaluate(operand, index, pipeline)
        case _:
            assert_never(node)
