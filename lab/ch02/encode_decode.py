"""encode, decode and the error handlers."""


def main() -> None:
    """Round-trip text through several codecs."""
    s = "所有权"
    for codec in ("utf-8", "utf-16", "utf-16-le", "gbk", "utf-32-le"):
        data = s.encode(codec)
        print(f"{codec:<10} {len(data):>2} {data.hex(' ')}")
        assert data.decode(codec) == s
    text = "café 所"
    for errors in ("ignore", "replace", "backslashreplace"):
        print(errors, text.encode("ascii", errors))
    print("xmlcharrefreplace", text.encode("ascii", "xmlcharrefreplace"))
    print("namereplace", text.encode("ascii", "namereplace"))
    bad = b"abc\xff\xfedef"
    print("replace", bad.decode("utf-8", errors="replace"))
    print("ignore", bad.decode("utf-8", errors="ignore"))
    escaped = bad.decode("utf-8", errors="surrogateescape")
    print("surrogateescape", ascii(escaped))
    print(escaped.encode("utf-8", errors="surrogateescape") == bad)
    print("bom", "x".encode("utf-8-sig"), b"\xef\xbb\xbfx".decode("utf-8-sig"))


if __name__ == "__main__":
    main()
