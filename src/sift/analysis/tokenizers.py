"""The three tokenizers: Latin only, CJK bigrams only, and both."""

import re
from collections.abc import Iterator

from sift.analysis.base import Analyzer
from sift.analysis.tokenize import CJK, Token, iter_tokens

_LATIN = re.compile(r"[0-9a-z_]+(?:\+{1,2}|\#)?", re.IGNORECASE)
_CJK_RUN = re.compile(f"[{CJK}]+")


class LatinTokenizer(Analyzer, name="latin"):
    """Yield Latin and digit runs; CJK text produces nothing.

    The text is not folded: offsets are into the argument and the
    token text keeps its case. Add NfkcCasefold to the pipeline.
    """

    def analyze(self, text: str) -> Iterator[Token]:
        """Yield one token per Latin or digit run."""
        for position, match in enumerate(_LATIN.finditer(text)):
            yield Token(match[0], position, match.start(), match.end())


class CjkBigramTokenizer(Analyzer, name="cjk-bigram"):
    """Yield overlapping bigrams of CJK runs; Latin text is skipped.

    A run of one character yields one unigram. The text is not
    folded, and offsets are into the argument.
    """

    def analyze(self, text: str) -> Iterator[Token]:
        """Yield the bigrams of every CJK run."""
        position = 0
        for match in _CJK_RUN.finditer(text):
            run = match[0]
            if len(run) == 1:
                yield Token(run, position, match.start(), match.end())
                position += 1
                continue
            for i in range(len(run) - 1):
                start = match.start() + i
                yield Token(run[i : i + 2], position, start, start + 2)
                position += 1


class MixedTokenizer(Analyzer, name="mixed"):
    """Latin words and CJK bigrams together: the ch05 iter_tokens.

    Unlike the other two it folds the text itself, so its offsets are
    into the NFKC-normalized, casefolded text.
    """

    def analyze(self, text: str) -> Iterator[Token]:
        """Yield the tokens of iter_tokens(text)."""
        return iter_tokens(text)
