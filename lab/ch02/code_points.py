"""A str is a sequence of code points, not of bytes."""

import unicodedata


def main() -> None:
    """Compare lengths, code points and names."""
    s = "所有权"
    print(f"{s!r}: len(s) = {len(s)}, bytes = {len(s.encode())}")
    for ch in s:
        print(f"  {ch} U+{ord(ch):04X} {unicodedata.name(ch)}")
    print(chr(0x6240) + chr(0x6709) + chr(0x6743))
    print("\N{CJK UNIFIED IDEOGRAPH-6240}", "\N{GREEK SMALL LETTER ALPHA}")
    print("\N{SNOWMAN}", "\u2603", "\U0001f600")
    for text in ("a", "é", "所", "😀"):
        utf8 = len(text.encode("utf-8"))
        utf16 = len(text.encode("utf-16-le"))
        print(f"{text!r}: len={len(text)} utf-8={utf8} utf-16={utf16}")
    composed = "é"
    decomposed = "e\u0301"
    print(len(composed), len(decomposed), composed == decomposed)
    print(unicodedata.category("a"), unicodedata.category("所"))
    print(unicodedata.category("１"), unicodedata.category("，"))


if __name__ == "__main__":
    main()
