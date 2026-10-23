"""Bit operations: masks, shifts, flags, counting, byte conversion."""

from sift.storage.segment import FLAG_ZLIB


def main() -> None:
    """Show the operators on small numbers."""
    a, b = 0b1100, 0b1010
    print(f"a      = {a:04b}")
    print(f"b      = {b:04b}")
    print(f"a & b  = {a & b:04b}")
    print(f"a | b  = {a | b:04b}")
    print(f"a ^ b  = {a ^ b:04b}")
    print(f"~a     = {~a} (= -a - 1), ~a & 0xF = {~a & 0xF:04b}")
    print(f"a << 2 = {a << 2:06b} ({a << 2}), a >> 2 = {a >> 2:b}")

    print("--- masks")
    n = 0xDEADBEEF
    print(f"n = {n:#x}")
    print(f"low byte   : {n & 0xFF:#04x}")
    print(f"high byte  : {(n >> 24) & 0xFF:#04x}")
    print(f"7-bit group: {n & 0x7F:#04x}, rest {n >> 7:#x}")

    print("--- negative numbers are infinite two's complement")
    print(f"-1 & 0xFF  = {-1 & 0xFF}")
    print(f"-2 & 0xFFFF = {-2 & 0xFFFF:#06x}")
    print(f"-1 >> 10   = {-1 >> 10}")
    print(
        f"(-5) .to_bytes(2, signed) = "
        f"{(-5).to_bytes(2, 'little', signed=True).hex(' ')}"
    )

    print("--- counting")
    n = 300
    print(f"{n}.bit_length() = {n.bit_length()}")
    print(f"{n}.bit_count()  = {n.bit_count()}")
    print("bytes needed as varint:", -(-n.bit_length() // 7))

    print("--- flags")
    flags = 0
    print("zlib flag set?", bool(flags & FLAG_ZLIB))
    flags |= FLAG_ZLIB
    print("after |=      ", bool(flags & FLAG_ZLIB), f"flags={flags:#06b}")
    flags &= ~FLAG_ZLIB
    print("after &= ~    ", bool(flags & FLAG_ZLIB), f"flags={flags:#06b}")
    flags ^= FLAG_ZLIB
    print("after ^=      ", bool(flags & FLAG_ZLIB))

    print("--- bytes and ints")
    raw = bytes.fromhex("2c010000")
    print("from_bytes little:", int.from_bytes(raw, "little"))
    print("from_bytes big   :", int.from_bytes(raw, "big"))
    print("to_bytes         :", (300).to_bytes(4, "little").hex(" "))

    print("--- one bit per document")
    present = 0
    for doc_id in (1, 4, 9):
        present |= 1 << doc_id
    print(
        f"bitset {present:#b}, docs:",
        [i for i in range(present.bit_length()) if present >> i & 1],
    )


if __name__ == "__main__":
    main()
