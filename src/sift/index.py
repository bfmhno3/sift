"""Inverted index, version 3: a Mapping of terms to postings."""

from bisect import bisect_left
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from operator import attrgetter
from types import TracebackType
from typing import Protocol, Self

from sift.analysis import Pipeline, Token, build_pipeline
from sift.document import Document

_DOC_ID: Callable[[Posting], int] = attrgetter("doc_id")


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

    @classmethod
    def from_sorted(cls, postings: list[Posting]) -> Self:
        """Wrap postings, already sorted by doc_id and unique.

        The list is kept, not copied, and not checked: it is for code
        that has just built it in order, such as unpickling.
        """
        out = cls()
        out._postings = postings
        return out

    def append(self, posting: Posting) -> None:
        """Add posting, whose doc_id must exceed every doc_id so far."""
        if self._postings and posting.doc_id <= self._postings[-1].doc_id:
            raise ValueError(f"doc_id {posting.doc_id} is not increasing")
        self._postings.append(posting)

    def extend(self, other: PostingList) -> None:
        """Add the postings of other, all after the ones here.

        The first doc_id of other must exceed the last one here.
        """
        if (
            self._postings
            and other._postings
            and other._postings[0].doc_id <= self._postings[-1].doc_id
        ):
            raise ValueError("doc_ids of other must come after self")
        self._postings.extend(other._postings)

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
        if not isinstance(doc_id, int):
            return False
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

    def __and__(self, other: object) -> PostingList:
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

    def __or__(self, other: object) -> PostingList:
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

    def without(self, doc_ids: Iterable[int]) -> PostingList:
        """Return a copy without the postings of doc_ids."""
        gone = set(doc_ids)
        out = PostingList()
        out._postings = [p for p in self._postings if p.doc_id not in gone]
        return out

    def __sub__(self, other: object) -> PostingList:
        """Return the documents of self that other lacks."""
        if not isinstance(other, PostingList):
            return NotImplemented
        out = PostingList()
        out._postings = [p for p in self._postings if p.doc_id not in other]
        return out


type _Wire = dict[str, list[tuple[int, tuple[int, ...]]]]
type _State = tuple[dict[int, Document], dict[int, int], _Wire, _Wire]


def _pack(postings: Mapping[str, PostingList]) -> _Wire:
    """Return postings as plain (doc_id, positions) tuples."""
    return {
        term: [(p.doc_id, p.positions) for p in plist]
        for term, plist in postings.items()
    }


def _unpack(wire: _Wire) -> dict[str, PostingList]:
    """Return the PostingLists of the output of _pack."""
    return {
        term: PostingList.from_sorted(
            [Posting(doc_id, pos) for doc_id, pos in pairs]
        )
        for term, pairs in wire.items()
    }


def _positions(tokens: Iterable[Token]) -> dict[str, list[int]]:
    """Group the positions of tokens by token text."""
    positions: dict[str, list[int]] = {}
    get = positions.get
    for token in tokens:
        found = get(token.text)
        if found is None:
            positions[token.text] = [token.position]
        else:
            found.append(token.position)
    return positions


def _append_postings(
    index: dict[str, PostingList],
    doc_id: int,
    positions: Mapping[str, list[int]],
) -> None:
    """Append one posting of doc_id to the list of every term.

    A PostingList is created only for a term met for the first time:
    building one costs a sort and a set, too much to throw away.
    """
    get = index.get
    for term, found in positions.items():
        posting = Posting(doc_id, tuple(found))
        plist = get(term)
        if plist is None:
            index[term] = plist = PostingList()
        plist.append(posting)


class PostingLookup(Protocol):
    """Anything that maps a term to its PostingList, with a default."""

    def get(self, term: str, default: PostingList, /) -> PostingList:
        """Return the postings of term, or default if it has none."""
        ...


class IndexView(PostingLookup, Protocol):
    """What Searcher and evaluate need from an index.

    InvertedIndex (in memory) and SegmentIndex (mmap) both conform;
    neither inherits from this class.
    """

    @property
    def documents(self) -> Mapping[int, Document]:
        """Return the live documents by doc_id."""
        ...

    @property
    def title_index(self) -> Mapping[str, PostingList]:
        """Return the index of the titles."""
        ...

    @property
    def n_docs(self) -> int:
        """Return the number of live documents."""
        ...

    @property
    def avg_doc_len(self) -> float:
        """Return the mean tokens per document."""
        ...

    def doc_len(self, doc_id: int) -> int:
        """Return the number of tokens indexed for doc_id."""
        ...

    def terms_with_prefix(self, prefix: str) -> list[str]:
        """Return the sorted body terms that start with prefix."""
        ...


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

    def __getstate__(self) -> _State:
        """Return the state to pickle, with postings as plain tuples.

        A Posting pickled as an object is rebuilt by a Python-level
        call per posting. Plain (doc_id, positions) tuples stay in the
        C pickler. On 60 posts (3.14.7): pickle.dumps took 65 ms
        against 284 ms and pickle.loads of the bare tuples 74 ms
        against 270 ms (about 4x). __setstate__ then builds the
        Posting objects, so loading the whole index took 197 ms
        against 270 ms (about 1.4x).
        """
        return (
            self.documents,
            self._doc_lens,
            _pack(self._postings),
            _pack(self.title_index),
        )

    def __setstate__(self, state: _State) -> None:
        """Rebuild the index from the state of __getstate__."""
        documents, doc_lens, body, titles = state
        self.documents = documents
        self._doc_lens = doc_lens
        self._postings = _unpack(body)
        self.title_index = _unpack(titles)
        self._sorted_terms = None

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
        _append_postings(self._postings, doc.doc_id, positions)
        _append_postings(
            self.title_index, doc.doc_id, _positions(title_tokens)
        )

    def merge(self, other: InvertedIndex) -> None:
        """Add every document of other, whose doc_ids all come later.

        The result is the index that add would have built by taking
        the documents of self, then those of other, in that order:
        same postings, same term order. other is only read. A doc_id
        of other that does not exceed every doc_id here raises
        ValueError and leaves self unchanged.
        """
        if (
            self.documents
            and other.documents
            and min(other.documents) <= max(self.documents)
        ):
            raise ValueError("doc_ids of other must come after self")
        self.documents.update(other.documents)
        self._doc_lens.update(other._doc_lens)
        self._sorted_terms = None
        for mine, theirs in (
            (self._postings, other._postings),
            (self.title_index, other.title_index),
        ):
            for term, plist in theirs.items():
                mine.setdefault(term, PostingList()).extend(plist)

    def remove(self, doc_ids: Iterable[int]) -> None:
        """Forget the documents in doc_ids, body and title postings.

        A term left without postings leaves the vocabulary. Ids that
        are not indexed are ignored. The cost is one pass over the
        whole vocabulary, however many documents are removed.
        """
        gone = set(doc_ids)
        for index in (self._postings, self.title_index):
            for term in list(index):
                kept = index[term].without(gone)
                if kept:
                    index[term] = kept
                else:
                    del index[term]
        for doc_id in gone:
            self.documents.pop(doc_id, None)
            self._doc_lens.pop(doc_id, None)
        self._sorted_terms = None

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


class IndexWriter:
    """A context manager that adds documents all or nothing.

    ::

        with IndexWriter(index) as writer:
            writer.add(doc)

    Leaving the block normally keeps the documents. Leaving it with
    an exception removes every document added inside the block, so
    the index is what it was before, and lets the exception go on.
    """

    def __init__(
        self, index: InvertedIndex, pipeline: Pipeline | None = None
    ) -> None:
        """Write into index, analyzing with pipeline (the default)."""
        self.index = index
        self.pipeline = pipeline or build_pipeline()
        self._added: list[int] = []

    def __enter__(self) -> Self:
        """Start a block with nothing added yet."""
        self._added.clear()
        return self

    def add(self, doc: Document) -> None:
        """Analyze the body and the title of doc and index them.

        A doc_id that is already indexed raises ValueError and is
        left alone, also by the rollback.
        """
        if doc.doc_id in self.index.documents:
            raise ValueError(f"doc_id {doc.doc_id} is already indexed")
        self._added.append(doc.doc_id)
        self.index.add(
            doc,
            self.pipeline.analyze(doc.body),
            self.pipeline.analyze(doc.title),
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Roll back on an exception; never swallow it."""
        if exc_type is not None:
            self.index.remove(self._added)
        self._added.clear()
