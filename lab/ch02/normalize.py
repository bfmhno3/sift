"""Unicode normalization forms and case folding."""

import unicodedata


def show(label: str, text: str) -> None:
    """Print text with its code points."""
    points = " ".join(f"U+{ord(c):04X}" for c in text)
    print(f"{label:<6} {text!r:<8} {points}")


def main() -> None:
    """Compare NFC, NFD, NFKC and NFKD on tricky inputs."""
    nfc = "\u00e9"
    nfd = "e\u0301"
    print(nfc == nfd, unicodedata.normalize("NFC", nfd) == nfc)
    for form in ("NFC", "NFD", "NFKC", "NFKD"):
        show(form, unicodedata.normalize(form, "\ufb01"))
    for form in ("NFC", "NFKC"):
        show(form, unicodedata.normalize(form, "\uff21\uff22\uff11"))
    show("NFKC", unicodedata.normalize("NFKC", "\u2460 \u00bd \u33a1"))
    show("NFKC", unicodedata.normalize("NFKC", "\u2160 \u2122"))
    print("ß".lower(), "ß".casefold(), "ß".upper())
    print("STRASSE".lower() == "straße".lower())
    print("STRASSE".casefold() == "straße".casefold())
    print("İ".lower().encode("unicode_escape"))
    word = "Ａｐｐｌｅ"
    print(word.casefold(), unicodedata.normalize("NFKC", word).casefold())


if __name__ == "__main__":
    main()
