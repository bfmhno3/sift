"""Narrowing: isinstance, TypeIs, TypeGuard, match, assert_never."""

from collections.abc import Sequence
from typing import Literal, TypeGuard, TypeIs, assert_never

from sift.query import And, Field, Node, Not, Or, Phrase, Prefix, Term


def length(value: str | list[int] | None) -> int:
    """Return len(value); None is 0. Each branch narrows the type."""
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.split())
    return len(value)


def is_str_list(value: Sequence[object]) -> TypeIs[list[str]]:
    """TypeIs: True means list[str], False means it is not."""
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def is_word_list(value: list[object]) -> TypeGuard[list[str]]:
    """TypeGuard: True means list[str]; False says nothing."""
    return all(isinstance(v, str) for v in value)


def join_words(value: Sequence[object]) -> str:
    """Join value if it is a list of str, else describe it."""
    if is_str_list(value):
        return " ".join(value)
    return f"not a list of str: {value!r}"


type Level = Literal["debug", "info", "warning"]


def number(level: Level) -> int:
    """Map a level to its number; the checker proves all are handled."""
    match level:
        case "debug":
            return 10
        case "info":
            return 20
        case "warning":
            return 30
        case _:
            assert_never(level)


def show(node: Node) -> str:
    """Render a query tree; a new Node class would fail type checking."""
    match node:
        case Term(text) | Prefix(text):
            return text
        case Phrase(words):
            return '"' + " ".join(words) + '"'
        case Field(name, value):
            return f"{name}:{show(value)}"
        case And(left, right):
            return f"({show(left)} AND {show(right)})"
        case Or(left, right):
            return f"({show(left)} OR {show(right)})"
        case Not(operand):
            return f"NOT {show(operand)}"
        case _:
            assert_never(node)


def main() -> None:
    """Exercise each narrowing form."""
    print(length(None), length("a b c"), length([1, 2]))
    print(join_words(["a", "b"]), join_words([1, "b"]))
    words: list[object] = ["x", "y"]
    if is_word_list(words):
        print(words[0].upper())
    print(number("info"))
    print(show(And(Term("rust"), Not(Phrase(("a", "b"))))))


if __name__ == "__main__":
    main()
