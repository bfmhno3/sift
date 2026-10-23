"""LEB128 varints: bytes for small and large numbers, deltas."""

from sift.storage.varint import decode, decode_deltas, encode, encode_deltas


def main() -> None:
    """Print the encoding of the numbers in the chapter."""
    print(f"{'n':>12}  {'bytes':>5}  hex")
    for n in (0, 1, 127, 128, 300, 16383, 16384, 2**32, 2**63):
        data = encode(n)
        print(f"{n:>12}  {len(data):>5}  {data.hex(' ')}")
        assert decode(data, 0) == (n, len(data))

    print("--- 300 by hand")
    n = 300
    low = n & 0x7F
    high = n >> 7
    print(f"300 = {n:#014b}; low 7 bits {low:07b}, rest {high:b}")
    print(
        f"first byte {low | 0x80:#04x} (continuation bit set), "
        f"second byte {high:#04x}"
    )

    print("--- doc ids as deltas")
    doc_ids = [3, 120, 125, 40000, 40001, 40010]
    plain = b"".join(encode(i) for i in doc_ids)
    packed = encode_deltas(doc_ids)
    print("doc ids      :", doc_ids)
    deltas = [b - a for a, b in zip([0, *doc_ids], doc_ids, strict=False)]
    print("deltas       :", deltas)
    print(f"as varints   : {len(plain)} bytes")
    print(f"as deltas    : {len(packed)} bytes")
    print(f"as u32       : {4 * len(doc_ids)} bytes")
    print("round trip   :", decode_deltas(packed, 0, len(doc_ids)))

    print("--- a stream: decode in a loop")
    stream = encode(5) + encode(300) + encode(0)
    pos = 0
    while pos < len(stream):
        value, pos = decode(stream, pos)
        print(f"value {value:>3}, next offset {pos}")

    print("--- errors")
    for bad in (b"\x80", b"\xff" * 11):
        try:
            decode(bad, 0)
        except ValueError as error:
            print("ValueError:", error)


if __name__ == "__main__":
    main()
