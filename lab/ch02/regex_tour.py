"""A tour of the re module, ending with the Sift tokenizer regex."""

import re

from sift.analysis.tokenize import _TOKEN


def main() -> None:
    """Run each feature on a small string."""
    text = "Python 3.14 shipped on 2025-10-07; 3.13 on 2024-10-07."
    num = re.compile(r"\d+(?:\.\d+)?")
    print(num.findall(text))
    print(num.search(text), num.fullmatch("3.14") is not None)
    date = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    m = date.search(text)
    assert m is not None
    print(m.groups(), m.group(0), m.span(1))
    named = re.compile(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")
    for m in named.finditer(text):
        print(m.groupdict(), m.start(), m.end())
    verbose = re.compile(
        r"""
        (?P<major>\d+) \.      # 主版本号
        (?P<minor>\d+)         # 次版本号
        """,
        re.VERBOSE,
    )
    print(verbose.findall(text))
    print(re.findall(r"\w+(?=;)", text), re.findall(r"\d+(?=;)", text))
    print(re.findall(r"(?<=on )\S+", text))
    print(date.sub(lambda m: f"{m[3]}/{m[2]}/{m[1]}", text))
    print(re.sub(r"\s+", " ", "a  b \n c"), re.split(r"[;,]\s*", "a; b,c"))
    html = "<b>one</b><b>two</b>"
    print(re.findall(r"<b>.*</b>", html), re.findall(r"<b>.*?</b>", html))
    print(re.findall(r"\bsift\b", "Sift sifted SIFT", re.IGNORECASE))
    print(re.findall(r"^\w+", "a b\nc d", re.MULTILINE))
    print(re.findall(r"\w+", "所有权 abc_1"), re.findall(r"\w+", "é", re.A))
    print(r"\d" == "\\d", len(r"\n"), len("\n"))
    print(_TOKEN.pattern)
    for m in _TOKEN.finditer("c++ 所有权 rust2"):
        print(m.lastgroup, m.group(), m.span())


if __name__ == "__main__":
    main()
