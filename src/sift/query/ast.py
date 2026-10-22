"""The query syntax tree: frozen dataclasses and one union alias."""

from dataclasses import dataclass
from typing import assert_never


@dataclass(frozen=True, slots=True)
class Term:
    """A word, analyzed when the query is evaluated."""

    text: str


@dataclass(frozen=True, slots=True)
class Prefix:
    """A word followed by ``*``: every term that starts with it."""

    text: str


@dataclass(frozen=True, slots=True)
class Phrase:
    """Words that must occur next to each other, in this order."""

    words: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Field:
    """A word or phrase restricted to one field."""

    name: str
    value: Node


@dataclass(frozen=True, slots=True)
class And:
    """Documents matching both sides."""

    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Or:
    """Documents matching either side."""

    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class Not:
    """Documents that do not match the operand."""

    operand: Node


type Node = Term | Prefix | Phrase | Field | And | Or | Not


def _level(node: Node) -> int:
    """Return how tightly node binds: Or 1, And 2, Not 3, rest 4."""
    match node:
        case Or():
            return 1
        case And():
            return 2
        case Not():
            return 3
        case _:
            return 4


def _print(node: Node, least: int) -> str:
    """Print node, in parentheses if it binds looser than least."""
    match node:
        case Term(text):
            out = text
        case Prefix(text):
            out = f"{text}*"
        case Phrase(words):
            out = f'"{" ".join(words)}"'
        case Field(name, value):
            out = f"{name}:{_print(value, 4)}"
        case Or(left, right):
            out = f"{_print(left, 1)} OR {_print(right, 2)}"
        case And(left, right):
            out = f"{_print(left, 2)} AND {_print(right, 3)}"
        case Not(operand):
            out = f"NOT {_print(operand, 3)}"
        case _:
            assert_never(node)
    return out if _level(node) >= least else f"({out})"


def print_query(node: Node) -> str:
    """Return query text that parses back to node.

    Operators are spelled out and parentheses appear only where the
    grammar needs them: ``parse(print_query(node)) == node`` for every
    tree whose words the lexer reads back as one word each.

    >>> print_query(And(Term("a"), Or(Term("b"), Not(Prefix("c")))))
    'a AND (b OR NOT c*)'
    >>> print_query(Field("title", Phrase(("x", "y"))))
    'title:"x y"'
    """
    return _print(node, 1)
