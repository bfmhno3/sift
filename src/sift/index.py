"""Inverted index, version 2: postings with positions."""

from bisect import bisect_left
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from operator import attrgetter

from sift.analysis.tokenize import Token
from sift.document import Document

_DOC_ID = attrgetter("doc_id")


@dataclass(frozen=True, slots=True)
class Posting:
    """One document in the posting list of a term.

    positions are the token positions of the term in the document,
    in increasing order.
    """

    doc_id: int
    positions: tuple[int, ...]

    @property
    def tf(self) -> int:
        """Return the term frequency: how often the term occurs."""
        return len(self.positions)


def _union(a: Posting, b: Posting) -> Posting:
    """Return the posting of a document found in both a and b."""
    merged = tuple(sorted({*a.positions, *b.positions}))
    return Posting(a.doc_id, merged)


class PostingList:
    """Postings sorted by doc_id, one per document, with set algebra.

    ``&`` keeps the documents in both operands, ``|`` the documents in
    either, ``-`` the documents of the left operand not in the right.
    A document found in both operands gets the sorted union of their
    positions.
    """

    def __init__(self, postings: Iterable[Posting] = ()) -> None:
        """Create a list from postings in any order."""
        self._postings = sorted(postings, key=_DOC_ID)
        ids = self.doc_ids()
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate doc_id in postings")

    def append(self, posting: Posting) -> None:
        """Add posting, whose doc_id must exceed every doc_id so far."""
        if self._postings and posting.doc_id <= self._postings[-1].doc_id:
            raise ValueError(f"doc_id {posting.doc_id} is not increasing")
        self._postings.append(posting)

    def doc_ids(self) -> list[int]:
        """Return the doc_ids in increasing order."""
        return [posting.doc_id for posting in self._postings]

    def __len__(self) -> int:
        """Return the number of documents in the list."""
        return len(self._postings)

    def __iter__(self) -> Iterator[Posting]:
        """Iterate over the postings in doc_id order."""
        return iter(self._postings)

    def __getitem__(self, i: int) -> Posting:
        """Return the i-th posting (not the posting of doc_id i)."""
        return self._postings[i]

    def __contains__(self, doc_id: object) -> bool:
        """Return True if some posting has this doc_id."""
        i = bisect_left(self._postings, doc_id, key=_DOC_ID)
        return i < len(self._postings) and self._postings[i].doc_id == doc_id

    def __repr__(self) -> str:
        """Return a repr that shows every posting."""
        return f"PostingList({self._postings!r})"

    def __eq__(self, other: object) -> bool:
        """Compare with another PostingList by postings."""
        if not isinstance(other, PostingList):
            return NotImplemented
        return self._postings == other._postings

    def __and__(self, other: PostingList) -> PostingList:
        """Return the documents found in both lists."""
        if not isinstance(other, PostingList):
            return NotImplemented
        out = PostingList()
        a, b = self._postings, other._postings
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i].doc_id < b[j].doc_id:
                i += 1
            elif a[i].doc_id > b[j].doc_id:
                j += 1
            else:
                out._postings.append(_union(a[i], b[j]))
                i += 1
                j += 1
        return out

    def __or__(self, other: PostingList) -> PostingList:
        """Return the documents found in either list."""
        if not isinstance(other, PostingList):
            return NotImplemented
        out = PostingList()
        a, b = self._postings, other._postings
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i].doc_id < b[j].doc_id:
                out._postings.append(a[i])
                i += 1
            elif a[i].doc_id > b[j].doc_id:
                out._postings.append(b[j])
                j += 1
            else:
                out._postings.append(_union(a[i], b[j]))
                i += 1
                j += 1
        out._postings.extend(a[i:])
        out._postings.extend(b[j:])
        return out

    def __sub__(self, other: PostingList) -> PostingList:
        """Return the documents of self that other lacks."""
        if not isinstance(other, PostingList):
            return NotImplemented
        out = PostingList()
        out._postings = [p for p in self._postings if p.doc_id not in other]
        return out


class InvertedIndex:
    """Map each term to the PostingList of the documents holding it."""

    def __init__(self) -> None:
        """Create an empty index."""
        self._postings: dict[str, PostingList] = {}

    def add(self, doc: Document, tokens: Iterable[Token]) -> None:
        """Index the tokens of one document.

        Documents must be added in increasing doc_id order. tokens may
        be a generator: it is consumed once.
        """
        positions: dict[str, list[int]] = {}
        for token in tokens:
            positions.setdefault(token.text, []).append(token.position)
        for term, found in positions.items():
            posting = Posting(doc.doc_id, tuple(found))
            self._postings.setdefault(term, PostingList()).append(posting)

    def __getitem__(self, term: str) -> PostingList:
        """Return the posting list of term; KeyError if unknown."""
        return self._postings[term]

    def __contains__(self, term: object) -> bool:
        """Return True if term occurs in at least one document."""
        return term in self._postings

    def __len__(self) -> int:
        """Return the number of distinct terms."""
        return len(self._postings)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the terms in the order they first appeared."""
        return iter(self._postings)
