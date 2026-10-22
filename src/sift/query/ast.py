"""The query syntax tree: frozen dataclasses and one union alias."""

from dataclasses import dataclass


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
