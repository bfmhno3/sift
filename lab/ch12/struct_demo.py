"""struct: pack and unpack binary records, byte order, alignment."""

import struct

from sift.storage.segment import HEADER, MAGIC


def main() -> None:
    """Show formats, endianness and padding."""
    data = struct.pack("<HI", 1, 300)
    print("pack('<HI', 1, 300):", data.hex(" "))
    print("unpack back        :", struct.unpack("<HI", data))
    print("big endian         :", struct.pack(">I", 300).hex(" "))
    print("little endian      :", struct.pack("<I", 300).hex(" "))

    print("--- size: '@' pads, '<' does not")
    for fmt in ("@BI", "<BI", "=BI", "@BQ", "<BQ", "@l", "<l", "@BH"):
        print(f"calcsize({fmt!r:6}) = {struct.calcsize(fmt)}")
    print("padded bytes @BI:", struct.pack("@BI", 1, 2).hex(" "))
    print("packed bytes <BI:", struct.pack("<BI", 1, 2).hex(" "))

    print("--- the segment header")
    print("format:", HEADER.format, "size:", HEADER.size)
    header = HEADER.pack(MAGIC, 1, 1, 123, 4567, 32 + 4 * 123, 9999)
    print("packed:", header.hex(" "))
    print("fields:", HEADER.unpack(header))

    print("--- unpack_from, iter_unpack, pack_into")
    blob = b"xx" + struct.pack("<3I", 10, 20, 30)
    print("unpack_from offset 2:", struct.unpack_from("<3I", blob, 2))
    print("iter_unpack         :", list(struct.iter_unpack("<I", blob[2:])))
    buf = bytearray(8)
    struct.pack_into("<HI", buf, 2, 7, 70000)
    print("pack_into           :", buf.hex(" "))

    print("--- errors")
    try:
        struct.pack("<H", 70000)
    except struct.error as error:
        print("struct.error:", error)
    try:
        struct.unpack("<I", b"abc")
    except struct.error as error:
        print("struct.error:", error)
    print("strings need a size:", struct.pack("<4s", b"SIFT"))
    print("int.to_bytes agrees:", (300).to_bytes(4, "little").hex(" "))


if __name__ == "__main__":
    main()
