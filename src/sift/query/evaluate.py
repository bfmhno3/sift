"""Evaluate a query tree against an index: postings in, postings out."""

from collections.abc import Mapping, Sequence
from typing import assert_never

from sift.analysis import Pipeline, build_pipeline
from sift.index import InvertedIndex, Posting, PostingList
from sift.query.ast import And, Field, Node, Not, Or, Phrase, Prefix, Term


def phrase_postings(
    lookup: Mapping[str, PostingList],
    terms: Sequence[str],
    offsets: Sequence[int] | None = None,
) -> PostingList:
    """Return the documents where terms occur at the given distances.

    offsets[k] is where term k sits relative to term 0; the default
    is consecutive positions, 0, 1, 2, and so on. A phrase whose
    stopwords were dropped passes the gaps they left.

    The posting of a match keeps the positions where the phrase
    starts, so its tf counts phrase occurrences. A single term is
    just its own posting list. Unlike ``&``, which merges the
    positions of both operands, this keeps each term's positions
    apart and shifts them: term k must sit at start + offsets[k].
    """
    if not terms:
        return PostingList()
    if offsets is None:
        offsets = range(len(terms))
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
            for start in (pos - offsets[driver] for pos in posting.positions)
            if start >= 0
            and all(
                start + offsets[k] in others[k][doc_id]
                for k in range(len(lists))
            )
        ]
        if starts:
            found.append(Posting(doc_id, tuple(starts)))
    return PostingList(found)


def _positioned(
    pipeline: Pipeline, words: Sequence[str]
) -> tuple[list[str], list[int]]:
    """Return the index terms of words and their relative positions.

    Each word is tokenized on its own; a word that a filter emptied
    (a stopword) still takes the positions its tokens had, so the
    next word sits where it would in the indexed text.
    """
    terms: list[str] = []
    offsets: list[int] = []
    base = 0
    for word in words:
        width = sum(1 for _ in pipeline.tokenizer.analyze(word))
        for token in pipeline.analyze(word):
            terms.append(token.text)
            offsets.append(base + token.position)
        base += width
    if offsets:
        first = offsets[0]
        offsets = [offset - first for offset in offsets]
    return terms, offsets


def _words(
    lookup: Mapping[str, PostingList], pipeline: Pipeline, words: Sequence[str]
) -> PostingList | None:
    """Return the phrase of words, or None if no word has a token."""
    terms, offsets = _positioned(pipeline, words)
    if not terms:
        return None
    return phrase_postings(lookup, terms, offsets)


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
) -> PostingList | None:
    """Evaluate ``name:value``; None if a title value has no tokens."""
    match name, value:
        case "title", Term(text):
            return _words(index.title_index, pipeline, [text])
        case "title", Phrase(words):
            return _words(index.title_index, pipeline, words)
        case _, Term(text):
            return _metadata_match(name, text, index)
        case _, Phrase(words):
            return _metadata_match(name, " ".join(words), index)
        case _:
            raise ValueError(f"bad field value: {value!r}")


def _prefix(
    text: str, index: InvertedIndex, pipeline: Pipeline
) -> PostingList | None:
    """Evaluate ``text*``: the last token is a prefix of index terms."""
    terms, offsets = _positioned(pipeline, [text])
    if not terms:
        return None
    *head, last = terms
    out = PostingList()
    for term in index.terms_with_prefix(last):
        out = out | phrase_postings(index, [*head, term], offsets)
    return out


def _eval(
    node: Node, index: InvertedIndex, pipeline: Pipeline
) -> PostingList | None:
    """Evaluate node; None means "no constraint" (only stopwords)."""
    match node:
        case Term(text):
            return _words(index, pipeline, [text])
        case Prefix(text):
            return _prefix(text, index, pipeline)
        case Phrase(words):
            return _words(index, pipeline, words)
        case Field(name, value):
            return _field(name, value, index, pipeline)
        case And(left, Not(operand)) | And(Not(operand), left):
            kept = _eval(left, index, pipeline)
            dropped = _eval(operand, index, pipeline)
            if kept is None or dropped is None:
                return kept
            return kept - dropped
        case And(left, right):
            a = _eval(left, index, pipeline)
            b = _eval(right, index, pipeline)
            return b if a is None else a if b is None else a & b
        case Or(left, right):
            a = _eval(left, index, pipeline)
            b = _eval(right, index, pipeline)
            return b if a is None else a if b is None else a | b
        case Not(operand):
            found = _eval(operand, index, pipeline)
            return None if found is None else _universe(index) - found
        case _:
            assert_never(node)


def evaluate(
    node: Node, index: InvertedIndex, pipeline: Pipeline | None = None
) -> PostingList:
    """Return the documents of index that match node.

    Words are analyzed with pipeline, which must be the one that
    built the index (default: build_pipeline()). A word that gives
    several tokens is a phrase of them. A word that gives none (a
    stopword) is ignored: it neither narrows an AND nor widens an OR,
    and a NOT of it does nothing; a phrase keeps the gap such a word
    leaves. A query that reduces to nothing matches no document. A
    NOT is the universe minus its operand, but ``x AND NOT y`` is
    computed as ``x - y`` without building the universe.
    """
    found = _eval(node, index, pipeline or build_pipeline())
    return PostingList() if found is None else found
