"""An exhaustive match: assert_never is the default case."""

from typing import assert_never

from sift.query import And, Field, Node, Not, Or, Phrase, Prefix, Term, parse


def show(node: Node) -> str:
    """Return node as query text, fully parenthesized."""
    match node:
        case Term(text):
            return text
        case Prefix(text):
            return f"{text}*"
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
    """Round-trip a query, then feed a non-node to the default case."""
    node = parse('tag:Rust "device tree" OR -latex owner*')
    text = show(node)
    print(text)
    assert parse(text) == node
    print("reparsed tree is equal")
    try:
        show("not a node")  # type: ignore[arg-type]
    except AssertionError as exc:
        print("assert_never raised:", exc)


if __name__ == "__main__":
    main()
