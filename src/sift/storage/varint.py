"""LEB128 unsigned varints and delta encoding.

A varint stores an integer in 7-bit groups, least significant group
first. The high bit of a byte says that another byte follows.

    >>> encode(300).hex()
    'ac02'
    >>> decode(b"\\xac\\x02", 0)
    (300, 2)
    >>> encode_deltas([3, 5, 9]).hex()
    '030204'
"""

from collections.abc import Iterable

# A 64-bit value needs ten groups; more is not a number we wrote.
MAX_BYTES = 10


def encode(n: int) -> bytes:
    """Return the LEB128 bytes of the non-negative integer n."""
    if n < 0:
        raise ValueError(f"varint cannot encode a negative number: {n}")
    out = bytearray()
    while n >= 0x80:
        out.append(n & 0x7F | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def decode(
    buf: bytes | bytearray | memoryview, offset: int
) -> tuple[int, int]:
    """Return ``(value, next_offset)`` of the varint at buf[offset].

    Raise ValueError if the buffer ends inside the varint or the
    varint is longer than MAX_BYTES. buf may also be an ``mmap``.
    """
    if offset < len(buf) and buf[offset] < 0x80:
        return buf[offset], offset + 1  # the common one-byte case
    value = 0
    shift = 0
    pos = offset
    while True:
        if pos >= len(buf):
            raise ValueError(f"truncated varint at offset {offset}")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7
        if pos - offset >= MAX_BYTES:
            raise ValueError(f"varint too long at offset {offset}")


def append_deltas(out: bytearray, seq: Iterable[int]) -> None:
    """Append the delta-coded varints of seq to out.

    Same bytes as ``out += encode_deltas(seq)``, without the
    intermediate bytes object. A delta below 0x80 is one byte and
    skips the call to encode.
    """
    previous = 0
    for n in seq:
        delta = n - previous
        if delta < 0:
            raise ValueError(f"sequence decreases: {previous} then {n}")
        if delta < 0x80:
            out.append(delta)
        else:
            out += encode(delta)
        previous = n


def encode_deltas(seq: Iterable[int]) -> bytes:
    """Return the varints of seq as differences between neighbours.

    The first number is stored as is. seq must not decrease; equal
    neighbours give a delta of 0.
    """
    out = bytearray()
    append_deltas(out, seq)
    return bytes(out)


def decode_deltas(
    buf: bytes | bytearray | memoryview, offset: int, count: int
) -> tuple[list[int], int]:
    """Return ``(numbers, next_offset)`` for count delta-coded varints."""
    numbers: list[int] = []
    total = 0
    for _ in range(count):
        delta, offset = decode(buf, offset)
        total += delta
        numbers.append(total)
    return numbers, offset
