"""Tests for sift.storage.segment: roundtrip and corruption."""

import struct
import tempfile
import zlib
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sift.errors import IndexCorruptError, IndexMissingError
from sift.index import Posting, PostingList
from sift.storage.segment import (
    FLAG_ZLIB,
    HEADER,
    Segment,
    read_header,
    write_segment,
)

TERMS = [
    ("alpha", PostingList([Posting(0, (0, 5, 9)), Posting(3, (2,))])),
    ("beta", PostingList([Posting(1, (1, 2))])),
    ("编译", PostingList([Posting(0, (7,)), Posting(2, (0, 1, 300))])),
]
LENGTHS = [10, 4, 7, 3]


def make(tmp_path: Path, *, compress: bool = False) -> Path:
    path = tmp_path / "segment.sft"
    write_segment(path, TERMS, LENGTHS, compress=compress)
    return path


@pytest.mark.parametrize("compress", [False, True])
def test_roundtrip(tmp_path: Path, compress: bool) -> None:
    path = make(tmp_path, compress=compress)
    with Segment(path) as segment:
        assert segment.compressed is compress
        assert segment.terms == ["alpha", "beta", "编译"]
        assert len(segment) == 3
        assert segment.n_docs == 4
        assert segment.doc_lens == tuple(LENGTHS)
        assert segment.doc_len(2) == 7
        for term, plist in TERMS:
            assert segment.postings(term) == plist
            assert segment.df(term) == len(plist)
        assert dict(segment.iter_postings()) == dict(TERMS)


def test_write_returns_the_file_size(tmp_path: Path) -> None:
    path = tmp_path / "segment.sft"
    assert write_segment(path, TERMS, LENGTHS) == path.stat().st_size


def test_header_fields(tmp_path: Path) -> None:
    data = make(tmp_path).read_bytes()
    magic, version, flags, n_docs, n_terms, dict_off, post_off = (
        HEADER.unpack_from(data)
    )
    assert (magic, version, flags, n_docs, n_terms) == (b"SIFT", 1, 0, 4, 3)
    assert dict_off == HEADER.size + 4 * 4
    assert post_off > dict_off


def test_lookup_and_prefix(tmp_path: Path) -> None:
    with Segment(make(tmp_path)) as segment:
        assert "beta" in segment
        assert "gamma" not in segment
        assert 3 not in segment
        assert segment.terms_with_prefix("a") == ["alpha"]
        assert segment.terms_with_prefix("") == segment.terms
        with pytest.raises(KeyError):
            segment.postings("gamma")
        with pytest.raises(KeyError):
            segment.df("gamma")


def test_empty_segment(tmp_path: Path) -> None:
    path = tmp_path / "segment.sft"
    write_segment(path, [], [])
    with Segment(path) as segment:
        assert len(segment) == 0
        assert segment.terms == []


def test_unsorted_terms_are_rejected(tmp_path: Path) -> None:
    reversed_terms = list(reversed(TERMS))
    with pytest.raises(ValueError, match="not sorted"):
        write_segment(tmp_path / "s.sft", reversed_terms, LENGTHS)
    assert not (tmp_path / "s.sft").exists()


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(IndexMissingError):
        Segment(tmp_path / "nope.sft")


def patched(tmp_path: Path, offset: int, new: bytes) -> Path:
    """Return a copy of the segment with bytes replaced at offset."""
    data = bytearray(make(tmp_path).read_bytes())
    data[offset : offset + len(new)] = new
    path = tmp_path / "bad.sft"
    path.write_bytes(data)
    return path


def test_bad_magic(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="bad magic"):
        Segment(patched(tmp_path, 0, b"NOPE"))


def test_bad_version(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="version 2"):
        Segment(patched(tmp_path, 4, struct.pack("<H", 2)))


def test_unknown_flags(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError, match="flags"):
        Segment(patched(tmp_path, 6, struct.pack("<H", 4)))


@pytest.mark.parametrize("size", [0, 5, HEADER.size - 1])
def test_truncated_header(tmp_path: Path, size: int) -> None:
    path = tmp_path / "short.sft"
    path.write_bytes(make(tmp_path).read_bytes()[:size])
    with pytest.raises(IndexCorruptError, match="truncated"):
        Segment(path)


def test_truncated_postings(tmp_path: Path) -> None:
    path = tmp_path / "cut.sft"
    path.write_bytes(make(tmp_path).read_bytes()[:-3])
    with pytest.raises(IndexCorruptError):
        Segment(path)


def test_offsets_outside_the_file(tmp_path: Path) -> None:
    big = struct.pack("<Q", 10**6)
    with pytest.raises(IndexCorruptError, match="offsets"):
        Segment(patched(tmp_path, 24, big))


def test_wrong_term_count(tmp_path: Path) -> None:
    with pytest.raises(IndexCorruptError):
        Segment(patched(tmp_path, 12, struct.pack("<I", 4)))


def test_garbled_posting_block(tmp_path: Path) -> None:
    path = make(tmp_path)
    data = bytearray(path.read_bytes())
    post_off = HEADER.unpack_from(data)[6]
    data[post_off : post_off + 2] = b"\xff\xff"
    path.write_bytes(data)
    with Segment(path) as segment:
        with pytest.raises(IndexCorruptError, match="alpha"):
            segment.postings("alpha")
        assert segment.postings("beta") == TERMS[1][1]


def test_garbled_zlib_block(tmp_path: Path) -> None:
    path = make(tmp_path, compress=True)
    data = bytearray(path.read_bytes())
    post_off = HEADER.unpack_from(data)[6]
    data[post_off + 3] ^= 0xFF
    path.write_bytes(data)
    with Segment(path) as segment, pytest.raises(IndexCorruptError):
        segment.postings("alpha")


def test_doc_id_past_the_slots(tmp_path: Path) -> None:
    path = tmp_path / "s.sft"
    write_segment(path, [("x", PostingList([Posting(9, (0,))]))], [1, 1])
    with (
        Segment(path) as segment,
        pytest.raises(IndexCorruptError, match="out of range"),
    ):
        segment.postings("x")


def test_flag_value_matches_the_format() -> None:
    assert FLAG_ZLIB == 1


def test_compressed_block_is_a_zlib_stream(tmp_path: Path) -> None:
    path = make(tmp_path, compress=True)
    data = path.read_bytes()
    with Segment(path) as segment:
        _, start, length = segment._entries[0]
    block = zlib.decompress(data[start : start + length])
    assert block[0] == 0  # first doc id delta


posting_lists = st.dictionaries(
    st.text(min_size=1, max_size=6),
    st.dictionaries(
        st.integers(0, 40),
        st.lists(st.integers(0, 5000), min_size=1, max_size=6).map(
            lambda xs: tuple(sorted(xs))
        ),
        min_size=1,
        max_size=8,
    ),
    max_size=12,
)


@given(posting_lists, st.booleans())
def test_roundtrip_property(data: dict, compress: bool) -> None:
    terms = [
        (term, PostingList(Posting(d, pos) for d, pos in docs.items()))
        for term, docs in sorted(data.items())
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "segment.sft"
        write_segment(path, terms, [1] * 41, compress=compress)
        with Segment(path) as segment:
            assert list(segment.iter_postings()) == terms


def test_blocks_can_be_copied_into_another_segment(tmp_path: Path) -> None:
    path = make(tmp_path, compress=True)
    other = tmp_path / "copy.sft"
    with Segment(path) as segment:
        write_segment(other, segment.iter_blocks(), LENGTHS)
    with Segment(other) as copy:
        assert not copy.compressed
        assert list(copy.iter_postings()) == TERMS


def test_read_header_checks_the_header_only(tmp_path: Path) -> None:
    path = make(tmp_path)
    header = read_header(path)
    assert (header.n_docs, header.n_terms, header.flags) == (4, 3, 0)
    with pytest.raises(IndexMissingError):
        read_header(tmp_path / "nope.sft")
    path.write_bytes(b"SIFT")
    with pytest.raises(IndexCorruptError, match="truncated"):
        read_header(path)
