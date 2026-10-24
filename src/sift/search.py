"""Search: parse, evaluate, score with BM25, build snippets."""

import time
import weakref
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sift.analysis import Pipeline, build_pipeline
from sift.cache import LRUCache
from sift.document import Document
from sift.index import IndexView, PostingList
from sift.query import (
    And,
    Node,
    Or,
    Phrase,
    Prefix,
    Term,
    evaluate,
    parse,
)
from sift.scoring import bm25, top_k
from sift.snippet import make_snippet


@dataclass(frozen=True, slots=True)
class Hit:
    """One ranked document with its snippet parts."""

    doc_id: int
    title: str
    path: Path
    score: float
    snippet: list[tuple[str, bool]]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The answer to a query: total matches and the best hits."""

    query: str
    total: int
    took_ms: float
    hits: list[Hit]


def positive_leaves(node: Node) -> list[Term | Prefix | Phrase]:
    """Return the body words and phrases that can raise a score.

    NOT subtrees contribute nothing, and neither do ``field:value``
    filters: they select documents but add no score.
    """
    match node:
        case Term() | Prefix() | Phrase():
            return [node]
        case And(left, right) | Or(left, right):
            return positive_leaves(left) + positive_leaves(right)
        case _:
            return []


class Searcher:
    """Run queries against an index and rank with BM25."""

    def __init__(
        self,
        index: IndexView,
        *,
        k1: float = 1.2,
        b: float = 0.75,
        pipeline: Pipeline | None = None,
        cache_size: int = 256,
        load: Callable[[int], Document] | None = None,
    ) -> None:
        """Keep the index and the BM25 parameters.

        pipeline must be the one that built the index; it defaults to
        build_pipeline(). cache_size is how many analyzed query words
        the LRU cache of ``term_cache`` keeps. load fetches a
        Document by doc id on a cache miss; it defaults to
        ``index.documents.__getitem__``.
        """
        self.index = index
        self.k1 = k1
        self.b = b
        self.pipeline = pipeline or build_pipeline()
        self.term_cache = LRUCache[str, tuple[str, ...]](cache_size)
        self._load = load or index.documents.__getitem__
        self.documents = weakref.WeakValueDictionary[int, Document]()
        self.doc_hits = 0
        self.doc_misses = 0

    def _document(self, doc_id: int) -> Document:
        """Return the Document of doc_id, shared while it is alive.

        ``documents`` holds weak references only: an entry vanishes
        when nothing else refers to its Document, so the cache never
        keeps a removed or replaced document alive. A hit is counted
        in ``doc_hits``, a miss in ``doc_misses``.
        """
        doc = self.documents.get(doc_id)
        if doc is None:
            self.doc_misses += 1
            doc = self._load(doc_id)
            self.documents[doc_id] = doc
        else:
            self.doc_hits += 1
        return doc

    def _terms(self, text: str) -> tuple[str, ...]:
        """Return the index terms of a query word, cached."""
        return self.term_cache.get_or_set(
            text, lambda word: tuple(self.pipeline.terms(word))
        )

    def _leaf(self, leaf: Term | Prefix | Phrase) -> PostingList:
        """Return the postings of one scoring leaf."""
        return evaluate(leaf, self.index, self.pipeline)

    def _highlight_terms(
        self, leaves: list[Term | Prefix | Phrase]
    ) -> set[str]:
        """Return the index terms to highlight for the leaves."""
        terms: set[str] = set()
        for leaf in leaves:
            match leaf:
                case Term(text):
                    terms.update(self._terms(text))
                case Phrase(words):
                    for word in words:
                        terms.update(self._terms(word))
                case Prefix(text):
                    tokens = self._terms(text)
                    terms.update(tokens[:-1])
                    if tokens:
                        found = self.index.terms_with_prefix(tokens[-1])
                        terms.update(found)
        return terms

    def search(self, query: str, limit: int = 10) -> SearchResult:
        """Return the best limit documents for query.

        The score of a document is the sum, over the positive leaves
        that match it, of ``bm25(tf, df, ...)``: for a phrase, tf is
        the number of occurrences and df the number of documents
        holding it. Raise QuerySyntaxError for a malformed query.
        """
        start = time.perf_counter()
        node = parse(query)
        matched = evaluate(node, self.index, self.pipeline)
        leaves = positive_leaves(node)
        index = self.index
        avg_len = index.avg_doc_len
        scores: dict[int, float] = defaultdict(float)
        for doc_id in matched.doc_ids():
            scores[doc_id] = 0.0
        for leaf in leaves:
            plist = self._leaf(leaf)
            df = len(plist)
            for posting in plist:
                if posting.doc_id not in matched:
                    continue
                scores[posting.doc_id] += bm25(
                    posting.tf,
                    df,
                    index.doc_len(posting.doc_id),
                    avg_len,
                    index.n_docs,
                    self.k1,
                    self.b,
                )
        terms = self._highlight_terms(leaves)
        hits: list[Hit] = []
        for doc_id, score in top_k(scores, limit):
            doc = self._document(doc_id)
            hits.append(
                Hit(
                    doc_id,
                    doc.title,
                    doc.path,
                    score,
                    make_snippet(doc.body, terms),
                )
            )
        took_ms = (time.perf_counter() - start) * 1000
        return SearchResult(query, len(matched), took_ms, hits)
