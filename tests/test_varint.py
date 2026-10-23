"""Tests for sift.storage.varint."""

import mmap

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sift.storage.varint import decode, decode_deltas, encode, encode_deltas


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, b"\x00"),
        (1, b"\x01"),
        (127, b"\x7f"),
        (128, b"\x80\x01"),
        (300, b"\xac\x02"),
        (2**32, b"\x80\x80\x80\x80\x10"),
    ],
)
def test_known_encodings(number: int, expected: bytes) -> None:
    assert encode(number) == expected
    assert decode(expected, 0) == (number, len(expected))


@given(st.integers(min_value=0, max_value=2**64 - 1))
def test_roundtrip(n: int) -> None:
    data = encode(n)
    assert decode(data, 0) == (n, len(data))


@given(
    st.lists(st.integers(min_value=0, max_value=2**40)),
    st.binary(max_size=8),
)
def test_decode_at_an_offset(numbers: list[int], prefix: bytes) -> None:
    data = prefix + b"".join(map(encode, numbers))
    pos = len(prefix)
    for n in numbers:
        value, pos = decode(data, pos)
        assert value == n
    assert pos == len(data)


@given(st.lists(st.integers(min_value=0, max_value=10**9)))
def test_delta_roundtrip(numbers: list[int]) -> None:
    numbers.sort()
    data = encode_deltas(numbers)
    assert decode_deltas(data, 0, len(numbers)) == (numbers, len(data))


def test_deltas_are_smaller_for_close_numbers() -> None:
    numbers = [1_000_000 + i for i in range(100)]
    assert len(encode_deltas(numbers)) < len(b"".join(map(encode, numbers)))


def test_negative_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        encode(-1)


def test_decreasing_sequence_is_rejected() -> None:
    with pytest.raises(ValueError, match="decreases"):
        encode_deltas([5, 4])


def test_truncated_varint() -> None:
    with pytest.raises(ValueError, match="truncated"):
        decode(b"\x80", 0)
    with pytest.raises(ValueError, match="truncated"):
        decode(b"", 0)


def test_overlong_varint() -> None:
    with pytest.raises(ValueError, match="too long"):
        decode(b"\xff" * 11, 0)


def test_decode_reads_an_mmap(tmp_path) -> None:
    path = tmp_path / "numbers.bin"
    path.write_bytes(encode(300) + encode(5))
    with (
        path.open("rb") as file,
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mapped,
    ):
        assert decode(mapped, 0) == (300, 2)
        assert decode(mapped, 2) == (5, 3)
