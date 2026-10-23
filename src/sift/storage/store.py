"""The index directory: build it, update it, open it.

An index directory holds three files::

    segment.sft    postings and document lengths (see segment.py)
    sift.db        pipeline, documents, query log (see db.py)
    manifest.json  what was indexed (see manifest.py); written last

The segment and the manifest are replaced atomically; the database
is updated in one transaction. ``update_index`` writes them and
``open_index`` returns a ``SegmentIndex``, which answers like an
``InvertedIndex`` but reads posting lists from the memory-mapped
segment when asked.
"""

import logging
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from sqlalchemy.exc import DatabaseError

from sift.analysis import Pipeline, build_pipeline
from sift.document import Document
from sift.errors import (
    FrontMatterError,
    IndexCorruptError,
    IndexMissingError,
    SiftError,
)
from sift.index import IndexWriter, InvertedIndex, Posting, PostingList
from sift.storage.db import load_documents, replace_documents
from sift.storage.manifest import (
    Change,
    Manifest,
    load_manifest,
    plan_update,
    save_manifest,
)
from sift.storage.segment import (
    Block,
    Segment,
    read_header,
    write_segment,
)

logger = logging.getLogger(__name__)

SEGMENT = "segment.sft"
DB = "sift.db"
MANIFEST = "manifest.json"


def _write_documents(
    path: Path,
    pipeline: Sequence[str],
    fresh: Iterable[Document],
    digests: Mapping[int, str],
    drop: set[int] | None,
) -> None:
    """Store the documents; start the database over if it is unusable.

    A file that is not a database (a crash, a stray copy) would make
    every later rebuild fail, so on a rebuild it is renamed to
    ``sift.db.corrupt`` (replacing an older one), which keeps the
    query log for recovery, and the write is retried once. An
    incremental update never gets here with such a file, because
    load_documents rejected it first.
    """
    fresh = list(fresh)
    try:
        replace_documents(path, pipeline, fresh, digests, drop=drop)
    except DatabaseError:
        if drop is not None:
            raise
        logger.warning("replacing the unusable database %s", path)
        path.replace(path.with_name(path.name + ".corrupt"))
        replace_documents(path, pipeline, fresh, digests, drop=None)


class SegmentIndex(Mapping[str, PostingList]):
    """An index served from a segment file, with InvertedIndex's API.

    ``index[term]`` decodes the posting list of term the first time
    and caches it. Body postings and document lengths come from the
    segment, the live documents from sift.db, and the title index is
    rebuilt from the titles (a few hundred tokens) when it is opened.
    """

    def __init__(
        self,
        segment: Segment,
        pipeline_names: Sequence[str],
        documents: dict[int, Document],
    ) -> None:
        """Wrap an open segment and its documents."""
        self._segment = segment
        self.pipeline_names = tuple(pipeline_names)
        self.documents = documents
        self._cache: dict[str, PostingList] = {}
        for doc_id in documents:
            if not 0 <= doc_id < segment.n_docs:
                raise IndexCorruptError(
                    f"{segment.path}: doc id {doc_id} has no length slot"
                )
        self.title_index = self._title_index(build_pipeline(pipeline_names))
        lengths = [segment.doc_len(doc_id) for doc_id in documents]
        self._total_len = sum(lengths)

    def _title_index(self, pipeline: Pipeline) -> dict[str, PostingList]:
        """Index the titles; positions count inside the title."""
        found: dict[str, PostingList] = {}
        for doc_id, doc in sorted(self.documents.items()):
            positions: dict[str, list[int]] = {}
            for token in pipeline.analyze(doc.title):
                positions.setdefault(token.text, []).append(token.position)
            for term, where in positions.items():
                posting = Posting(doc_id, tuple(where))
                found.setdefault(term, PostingList()).append(posting)
        return found

    @property
    def segment(self) -> Segment:
        """Return the underlying segment."""
        return self._segment

    def terms_with_prefix(self, prefix: str) -> list[str]:
        """Return the sorted body terms that start with prefix."""
        return self._segment.terms_with_prefix(prefix)

    def doc_len(self, doc_id: int) -> int:
        """Return the number of tokens indexed for doc_id."""
        return self._segment.doc_len(doc_id)

    @property
    def n_docs(self) -> int:
        """Return the number of live documents."""
        return len(self.documents)

    @property
    def avg_doc_len(self) -> float:
        """Return the mean tokens per live document (0.0 when empty)."""
        if not self.documents:
            return 0.0
        return self._total_len / len(self.documents)

    def __getitem__(self, term: str) -> PostingList:
        """Return the posting list of term; KeyError if unknown."""
        plist = self._cache.get(term)
        if plist is None:
            plist = self._cache[term] = self._segment.postings(term)
        return plist

    def __contains__(self, term: object) -> bool:
        """Return True if term has postings, without decoding them."""
        return term in self._segment

    def __len__(self) -> int:
        """Return the number of distinct terms."""
        return len(self._segment)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the terms in sorted order."""
        return iter(self._segment.terms)

    def close(self) -> None:
        """Unmap the segment."""
        self._segment.close()

    def __enter__(self) -> Self:
        """Return the open index."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Unmap the segment."""
        self.close()


def open_index(index_dir: Path) -> SegmentIndex:
    """Open the index in index_dir.

    Raise IndexMissingError if there is no segment there and
    IndexCorruptError if a file of the index fails its checks.
    """
    segment_path = index_dir / SEGMENT
    if not segment_path.is_file():
        raise IndexMissingError(
            f"no index at {index_dir}, run 'sift index' first"
        )
    names, documents = load_documents(index_dir / DB)
    segment = Segment(segment_path)
    try:
        return SegmentIndex(segment, names, documents)
    except BaseException:
        segment.close()
        raise


@dataclass(frozen=True, slots=True)
class UpdateReport:
    """What ``update_index`` did."""

    full: bool
    parsed: int
    unchanged: int
    removed: int
    documents: int
    terms: int
    size: int


def _read_old(
    index_dir: Path, corpus: Path, names: Sequence[str]
) -> tuple[Manifest, dict[int, Document]] | None:
    """Return the manifest and documents to update, or None to rebuild.

    Only the headers and the small files are read here; the segment
    itself is mapped later, if the update needs it.
    """
    try:
        manifest = load_manifest(index_dir / MANIFEST)
        read_header(index_dir / SEGMENT)
        old_names, documents = load_documents(index_dir / DB)
    except IndexMissingError:
        return None
    except IndexCorruptError as error:
        logger.warning("rebuilding, the old index is unusable: %s", error)
        return None
    if Path(
        manifest.corpus
    ).resolve() != corpus.resolve() or old_names != list(names):
        logger.info("rebuilding: corpus or pipeline changed")
        return None
    return manifest, documents


def _parse(corpus: Path, changes: list[Change]) -> list[Document]:
    """Parse the changed files; raise one ExceptionGroup on failures."""
    documents: list[Document] = []
    errors: list[FrontMatterError] = []
    for change in changes:
        path = corpus / change.relpath
        text = path.read_text(encoding="utf-8")
        try:
            doc = Document.from_markdown(change.entry.doc_id, path, text)
        except FrontMatterError as error:
            errors.append(error)
        else:
            documents.append(doc)
    if errors:
        noun = "file" if len(errors) == 1 else "files"
        raise ExceptionGroup(f"{len(errors)} {noun} failed", errors)
    return documents


def _merged(
    old: Segment | None,
    old_docs: Mapping[int, Document],
    stale: set[int],
    fresh: InvertedIndex,
    pipeline: Pipeline,
) -> list[tuple[str, PostingList | Block]]:
    """Merge the old postings (minus stale ids) with the fresh ones.

    Only the terms of the stale documents (found by analyzing their
    old bodies) and of the fresh documents can change. Every other
    term keeps its encoded block untouched.
    """
    merged: dict[str, PostingList | Block] = {}
    if old is not None:
        affected = set(fresh)
        for doc_id in stale & old_docs.keys():
            affected.update(pipeline.terms(old_docs[doc_id].body))
        for term, block in old.iter_blocks():
            if term not in affected:
                merged[term] = block
                continue
            kept = old.parse_block(term, block).without(stale)
            if kept:
                merged[term] = kept
    for term, plist in fresh.items():
        known = merged.get(term)
        if isinstance(known, PostingList):
            plist = known | plist
        merged[term] = plist
    return sorted(merged.items())


def update_index(
    corpus: Path,
    index_dir: Path,
    pipeline_names: Sequence[str],
    *,
    full: bool = False,
    compress: bool = False,
) -> UpdateReport:
    """Build or update the index of corpus in index_dir.

    Without full, only new and changed files are parsed and analyzed;
    their postings are merged with the old ones, minus the postings of
    changed and deleted files, and the other terms are copied as
    encoded. The index is rebuilt from scratch when full is set, when
    there is no usable index, or when the corpus path or the pipeline
    differs from the old one. Malformed front matter raises an
    ExceptionGroup before anything is written.
    """
    if not corpus.is_dir():
        raise SiftError(f"no corpus at {corpus}")
    pipeline = build_pipeline(pipeline_names)
    index_dir.mkdir(parents=True, exist_ok=True)
    state = None if full else _read_old(index_dir, corpus, pipeline_names)
    manifest, old_docs = state if state else (None, {})
    plan = plan_update(corpus, manifest)
    if state and not (plan.reparse or plan.removed):
        header = read_header(index_dir / SEGMENT)
        save_manifest(index_dir / MANIFEST, plan.manifest)
        size = (index_dir / SEGMENT).stat().st_size
        return UpdateReport(
            False, 0, plan.unchanged, 0, len(old_docs), header.n_terms, size
        )
    fresh = InvertedIndex()
    with IndexWriter(fresh, pipeline) as writer:
        for doc in _parse(corpus, plan.reparse):
            writer.add(doc)
    stale = plan.stale_ids
    documents = {
        doc_id: doc for doc_id, doc in old_docs.items() if doc_id not in stale
    }
    documents.update(fresh.documents)
    old = Segment(index_dir / SEGMENT) if state else None
    try:
        lengths = [0] * plan.manifest.next_doc_id
        for doc_id in documents:
            if doc_id in fresh.documents:
                lengths[doc_id] = fresh.doc_len(doc_id)
            else:
                assert old is not None
                lengths[doc_id] = old.doc_len(doc_id)
        terms = _merged(old, old_docs, stale, fresh, pipeline)
        size = write_segment(
            index_dir / SEGMENT, terms, lengths, compress=compress
        )
    finally:
        if old is not None:
            old.close()
    digests = {e.doc_id: e.sha256 for e in plan.manifest.files.values()}
    _write_documents(
        index_dir / DB,
        pipeline_names,
        fresh.documents.values(),
        digests,
        stale if state else None,
    )
    save_manifest(index_dir / MANIFEST, plan.manifest)
    return UpdateReport(
        state is None,
        len(plan.reparse),
        plan.unchanged,
        len(plan.removed),
        len(documents),
        len(terms),
        size,
    )
