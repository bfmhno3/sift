"""Inverted index, version 3: a Mapping of terms to postings."""

from bisect import bisect_left
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from operator import attrgetter

from sift.analysis import Token
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


def _positions(tokens: Iterable[Token]) -> dict[str, list[int]]:
    """Group the positions of tokens by token text."""
    positions: dict[str, list[int]] = {}
    for token in tokens:
        positions.setdefault(token.text, []).append(token.position)
    return positions


class InvertedIndex(Mapping[str, PostingList]):
    """Map each term to the PostingList of the documents holding it.

    Only __getitem__, __iter__ and __len__ are written here; Mapping
    supplies keys, items, values, get, __contains__ and __eq__.

    The Mapping itself covers the body of the documents. The titles
    live in a second, smaller index, ``title_index``, with the same
    layout (term to PostingList, positions counted inside the title),
    so ``title:`` queries and title phrases reuse the same code.
    """

    def __init__(self) -> None:
        """Create an empty index."""
        self._postings: dict[str, PostingList] = {}
        self._doc_lens: dict[int, int] = {}
        self.documents: dict[int, Document] = {}
        self.title_index: dict[str, PostingList] = {}
        self._sorted_terms: list[str] | None = None

    def add(
        self,
        doc: Document,
        tokens: Iterable[Token],
        title_tokens: Iterable[Token] = (),
    ) -> None:
        """Index the tokens of one document.

        Documents must be added in increasing doc_id order. tokens and
        title_tokens may be generators: each is consumed once. The
        title tokens go into title_index and do not count toward the
        document length.
        """
        positions = _positions(tokens)
        length = sum(len(found) for found in positions.values())
        self.documents[doc.doc_id] = doc
        self._doc_lens[doc.doc_id] = length
        self._sorted_terms = None
        for term, found in positions.items():
            posting = Posting(doc.doc_id, tuple(found))
            self._postings.setdefault(term, PostingList()).append(posting)
        for term, found in _positions(title_tokens).items():
            posting = Posting(doc.doc_id, tuple(found))
            self.title_index.setdefault(term, PostingList()).append(posting)

    def terms_with_prefix(self, prefix: str) -> list[str]:
        """Return the sorted body terms that start with prefix.

        The sorted vocabulary is built on the first call after an
        add and found by bisection: every term with the prefix lies
        between prefix and prefix followed by the largest code point.
        """
        if self._sorted_terms is None:
            self._sorted_terms = sorted(self._postings)
        terms = self._sorted_terms
        lo = bisect_left(terms, prefix)
        hi = bisect_left(terms, prefix + "\U0010ffff")
        return terms[lo:hi]

    def doc_len(self, doc_id: int) -> int:
        """Return the number of tokens indexed for doc_id."""
        return self._doc_lens[doc_id]

    @property
    def n_docs(self) -> int:
        """Return the number of documents added."""
        return len(self.documents)

    @property
    def avg_doc_len(self) -> float:
        """Return the mean tokens per document (0.0 when empty)."""
        if not self._doc_lens:
            return 0.0
        return sum(self._doc_lens.values()) / len(self._doc_lens)

    def __getitem__(self, term: str) -> PostingList:
        """Return the posting list of term; KeyError if unknown."""
        return self._postings[term]

    def __len__(self) -> int:
        """Return the number of distinct terms."""
        return len(self._postings)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the terms in the order they first appeared."""
        return iter(self._postings)
