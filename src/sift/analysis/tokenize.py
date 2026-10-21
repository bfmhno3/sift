"""The chapter 2 tokenizer: Latin words and CJK bigrams."""

import re
import unicodedata

CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"

# Latin/digit run with an optional c++ / c# style suffix, or a CJK run.
_TOKEN = re.compile(
    rf"""
    (?P<latin> [0-9a-z_]+ (?: \+{{1,2}} | \# )? )
    | (?P<cjk> [{CJK}]+ )
    """,
    re.VERBOSE,
)


def tokenize(text: str) -> list[str]:
    """Split text into index terms.

    The text is NFKC-normalized and casefolded first. Latin and digit
    runs become one token each (``c++`` and ``c#`` keep their suffix).
    A CJK run becomes overlapping bigrams, or one unigram when the run
    has a single character.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    for match in _TOKEN.finditer(folded):
        if match["latin"] is not None:
            tokens.append(match["latin"])
            continue
        run = match["cjk"]
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens
