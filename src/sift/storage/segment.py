"""The segment file: terms, postings and document lengths on disk.

All numbers are little-endian. The file is laid out as::

    header   magic b"SIFT" | version u16 | flags u16 | n_docs u32
             | n_terms u32 | dict_off u64 | post_off u64
    doclens  n_docs x u32 token counts, indexed by doc_id
    dict     per term, in sorted order: varint len | utf-8 bytes
             | varint df | varint post_rel_off | varint post_len
    postings per term: per document, varint doc_id delta | varint tf
             | tf x varint position delta (zlib-compressed per term
             when flag bit 0 is set)

doc ids are stable but not dense once files are deleted, so n_docs
counts slots: ids run from 0 to n_docs - 1 and a deleted id has the
length 0. The live documents are listed in ``docs.json``, not here.

The reader maps the file with ``mmap``. It scans the dictionary once
(a few hundred bytes per thousand terms) and bisects the sorted terms;
a posting list is decoded only when a query asks for it.
"""

import bisect
import mmap
import struct
import zlib
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from sift.errors import IndexCorruptError, IndexMissingError
from sift.index import Posting, PostingList
from sift.storage.atomic import atomic_write
from sift.storage.varint import decode, decode_deltas, encode, encode_deltas

MAGIC = b"SIFT"
VERSION = 1
FLAG_ZLIB = 1
HEADER = struct.Struct("<4sHHIIQQ")


@dataclass(frozen=True, slots=True)
class Block:
    """The encoded postings of one term, ready to be written again.

    data is the block before compression. Copying a Block into a new
    segment skips decoding and encoding the posting list, which is
    what makes an incremental update cheap for untouched terms.
    """

    df: int
    data: bytes


@dataclass(frozen=True, slots=True)
class Header:
    """The checked fields of a segment header."""

    flags: int
    n_docs: int
    n_terms: int
    dict_off: int
    post_off: int


def parse_header(data: bytes | mmap.mmap, size: int, path: Path) -> Header:
    """Check the header at the start of data; size is the file size.

    Raise IndexCorruptError naming path for a short file, a wrong
    magic or version, unknown flags or offsets that do not fit.
    """

    def fail(message: str) -> IndexCorruptError:
        return IndexCorruptError(f"{path}: {message}")

    if size < HEADER.size:
        raise fail("truncated header")
    magic, version, flags, n_docs, n_terms, dict_off, post_off = (
        HEADER.unpack_from(data, 0)
    )
    if magic != MAGIC:
        raise fail(f"bad magic {magic!r}, expected {MAGIC!r}")
    if version != VERSION:
        raise fail(f"unsupported version {version}")
    if flags & ~FLAG_ZLIB:
        raise fail(f"unknown flags {flags:#x}")
    if dict_off != HEADER.size + 4 * n_docs:
        raise fail("dictionary offset does not follow doclens")
    if not dict_off <= post_off <= size:
        raise fail("offsets outside the file")
    return Header(flags, n_docs, n_terms, dict_off, post_off)


def read_header(path: Path) -> Header:
    """Read and check only the header of the segment at path.

    Raise IndexMissingError if the file does not exist.
    """
    try:
        with path.open("rb") as file:
            head = file.read(HEADER.size)
            size = file.seek(0, 2)
    except FileNotFoundError:
        raise IndexMissingError(f"no segment at {path}") from None
    return parse_header(head, size, path)


def _encode_postings(plist: PostingList) -> bytes:
    """Return the postings block of one term, before compression."""
    out = bytearray()
    previous = 0
    for posting in plist:
        out += encode(posting.doc_id - previous)
        out += encode(posting.tf)
        out += encode_deltas(posting.positions)
        previous = posting.doc_id
    return bytes(out)


def write_segment(
    path: Path,
    terms: Iterable[tuple[str, PostingList | Block]],
    doc_lens: Sequence[int],
    *,
    compress: bool = False,
) -> int:
    """Write a segment file atomically and return its size in bytes.

    terms must come in strictly increasing order (code point order,
    the same as UTF-8 byte order); each value is a PostingList or an
    already encoded Block. doc_lens has one length per doc id slot.
    With compress each term's postings block goes through zlib.
    """
    dictionary = bytearray()
    postings = bytearray()
    n_terms = 0
    previous: str | None = None
    for term, value in terms:
        if previous is not None and term <= previous:
            raise ValueError(f"terms not sorted: {previous!r}, {term!r}")
        previous = term
        if isinstance(value, Block):
            df, block = value.df, value.data
        else:
            df, block = len(value), _encode_postings(value)
        if compress:
            block = zlib.compress(block)
        raw = term.encode("utf-8")
        dictionary += encode(len(raw)) + raw
        dictionary += encode(df)
        dictionary += encode(len(postings)) + encode(len(block))
        postings += block
        n_terms += 1
    dict_off = HEADER.size + 4 * len(doc_lens)
    post_off = dict_off + len(dictionary)
    header = HEADER.pack(
        MAGIC,
        VERSION,
        FLAG_ZLIB if compress else 0,
        len(doc_lens),
        n_terms,
        dict_off,
        post_off,
    )
    lengths = struct.pack(f"<{len(doc_lens)}I", *doc_lens)
    atomic_write(path, [header, lengths, dictionary, postings])
    return post_off + len(postings)


class Segment:
    """A read-only, memory-mapped segment file.

    Open it with ``with Segment(path) as segment``. A missing file
    raises IndexMissingError. A file whose magic, version, offsets or
    dictionary do not check out raises IndexCorruptError, and so does
    any posting list that fails to decode later.
    """

    def __init__(self, path: Path) -> None:
        """Map path and read its header, doc lengths and dictionary."""
        self.path = path
        try:
            file = path.open("rb")
        except FileNotFoundError:
            raise IndexMissingError(f"no segment at {path}") from None
        with file:
            size = file.seek(0, 2)
            if size < HEADER.size:
                raise IndexCorruptError(f"{path}: truncated header")
            self._map = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        self.size = size
        try:
            self._read_header()
            self._read_dictionary()
        except BaseException:
            self._map.close()
            raise

    def _fail(self, message: str) -> IndexCorruptError:
        """Return an IndexCorruptError that names the file."""
        return IndexCorruptError(f"{self.path}: {message}")

    def _read_header(self) -> None:
        """Check the header and load the document lengths."""
        header = parse_header(self._map, self.size, self.path)
        self.compressed = bool(header.flags & FLAG_ZLIB)
        self.n_terms = header.n_terms
        self._dict_off = header.dict_off
        self._post_off = header.post_off
        self.doc_lens: tuple[int, ...] = struct.unpack_from(
            f"<{header.n_docs}I", self._map, HEADER.size
        )

    def _read_dictionary(self) -> None:
        """Scan the dictionary into sorted terms and entry tuples."""
        base = self._dict_off
        block = self._map[base : self._post_off]
        terms: list[str] = []
        entries: list[tuple[int, int, int]] = []
        pos = 0
        end = len(block)
        try:
            for _ in range(self.n_terms):
                length, pos = decode(block, pos)
                stop = pos + length
                if stop > end:
                    raise ValueError("term runs past the dictionary")
                term = block[pos:stop].decode("utf-8")
                pos = stop
                df, pos = decode(block, pos)
                rel, pos = decode(block, pos)
                post_len, pos = decode(block, pos)
                if terms and term <= terms[-1]:
                    raise ValueError(f"terms not sorted at {term!r}")
                if self._post_off + rel + post_len > self.size:
                    raise ValueError(f"postings of {term!r} past the end")
                terms.append(term)
                entries.append((df, self._post_off + rel, post_len))
        except ValueError as error:
            raise self._fail(f"bad dictionary: {error}") from None
        if pos != end:
            raise self._fail("dictionary does not end at the postings")
        self.terms = terms
        self._entries = entries

    @property
    def n_docs(self) -> int:
        """Return the number of doc id slots (live or deleted)."""
        return len(self.doc_lens)

    def doc_len(self, doc_id: int) -> int:
        """Return the token count of doc_id (0 for an empty slot)."""
        return self.doc_lens[doc_id]

    def _find(self, term: str) -> int:
        """Return the dictionary position of term, or -1."""
        i = bisect.bisect_left(self.terms, term)
        if i < len(self.terms) and self.terms[i] == term:
            return i
        return -1

    def __len__(self) -> int:
        """Return the number of terms."""
        return self.n_terms

    def __contains__(self, term: object) -> bool:
        """Return True if term has a posting list."""
        return isinstance(term, str) and self._find(term) >= 0

    def df(self, term: str) -> int:
        """Return the document frequency of term; KeyError if absent."""
        i = self._find(term)
        if i < 0:
            raise KeyError(term)
        return self._entries[i][0]

    def terms_with_prefix(self, prefix: str) -> list[str]:
        """Return the sorted terms that start with prefix."""
        lo = bisect.bisect_left(self.terms, prefix)
        hi = bisect.bisect_left(self.terms, prefix + "\U0010ffff")
        return self.terms[lo:hi]

    def postings(self, term: str) -> PostingList:
        """Decode and return the posting list of term.

        Raise KeyError if the term is absent and IndexCorruptError if
        its block does not decode.
        """
        i = self._find(term)
        if i < 0:
            raise KeyError(term)
        return self.parse_block(term, self._block(term, i))

    def iter_postings(self) -> Iterator[tuple[str, PostingList]]:
        """Yield every term with its posting list, in sorted order."""
        for term, block in self.iter_blocks():
            yield term, self.parse_block(term, block)

    def iter_blocks(self) -> Iterator[tuple[str, Block]]:
        """Yield every term with its undecoded Block, in sorted order."""
        for i, term in enumerate(self.terms):
            yield term, self._block(term, i)

    def _block(self, term: str, i: int) -> Block:
        """Return the (decompressed) block of the i-th term."""
        df, start, length = self._entries[i]
        data = self._map[start : start + length]
        if self.compressed:
            try:
                data = zlib.decompress(data)
            except zlib.error as error:
                raise self._fail(
                    f"bad postings of {term!r}: {error}"
                ) from None
        return Block(df, data)

    def parse_block(self, term: str, block: Block) -> PostingList:
        """Decode the posting list in block, found under term."""
        data = block.data
        try:
            plist = PostingList()
            pos = 0
            doc_id = 0
            for _ in range(block.df):
                delta, pos = decode(data, pos)
                doc_id += delta
                tf, pos = decode(data, pos)
                positions, pos = decode_deltas(data, pos, tf)
                if doc_id >= self.n_docs:
                    raise ValueError(f"doc id {doc_id} out of range")
                plist.append(Posting(doc_id, tuple(positions)))
            if pos != len(data):
                raise ValueError("bytes left over after the last posting")
        except ValueError as error:
            raise self._fail(f"bad postings of {term!r}: {error}") from None
        return plist

    def close(self) -> None:
        """Unmap the file."""
        self._map.close()

    def __enter__(self) -> Self:
        """Return the open segment."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Unmap the file."""
        self.close()
