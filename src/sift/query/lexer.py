"""The query lexer: a generator of tokens."""

from collections.abc import Iterator
from enum import Enum, auto
from typing import NamedTuple

from sift.query.errors import QuerySyntaxError

FIELDS = frozenset({"title", "tag", "category", "series"})
_OPERATORS = frozenset({"AND", "OR", "NOT"})
_STOP = frozenset('()"*')


class Kind(Enum):
    """The kinds of query token."""

    WORD = auto()
    PHRASE = auto()
    FIELD = auto()
    LPAREN = auto()
    RPAREN = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    MINUS = auto()
    STAR = auto()
    EOF = auto()


class QToken(NamedTuple):
    """One query token: its kind, its text and where it starts."""

    kind: Kind
    text: str
    pos: int


_SINGLE = {
    "(": Kind.LPAREN,
    ")": Kind.RPAREN,
    "*": Kind.STAR,
}


def _word_end(query: str, start: int) -> int:
    """Return the offset where the word that starts at start ends."""
    end = start
    while end < len(query):
        ch = query[end]
        if ch.isspace() or ch in _STOP:
            break
        if ch == ":" and query[start:end] in FIELDS:
            break
        end += 1
    return end


def iter_tokens(query: str) -> Iterator[QToken]:
    """Yield the tokens of query, then one EOF token.

    A ``-`` that starts a token is MINUS; inside a word it is a
    letter of the word. ``AND``, ``OR`` and ``NOT`` are operators
    only in upper case. A word followed by a colon is a FIELD when
    it names one of FIELDS, and a plain word otherwise (``a:b``).
    An unterminated quote raises QuerySyntaxError.
    """
    i = 0
    while i < len(query):
        ch = query[i]
        if ch.isspace():
            i += 1
        elif ch in _SINGLE:
            yield QToken(_SINGLE[ch], ch, i)
            i += 1
        elif ch == '"':
            close = query.find('"', i + 1)
            if close == -1:
                raise QuerySyntaxError("unterminated phrase", query, i)
            yield QToken(Kind.PHRASE, query[i + 1 : close], i)
            i = close + 1
        elif ch == "-":
            yield QToken(Kind.MINUS, ch, i)
            i += 1
        else:
            end = _word_end(query, i)
            word = query[i:end]
            if word in _OPERATORS:
                yield QToken(Kind[word], word, i)
            elif end < len(query) and query[end] == ":" and word in FIELDS:
                yield QToken(Kind.FIELD, word, i)
                end += 1
            else:
                yield QToken(Kind.WORD, word, i)
            i = end
    yield QToken(Kind.EOF, "", len(query))
