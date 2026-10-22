"""Structural pattern matching: every kind of pattern once."""

from dataclasses import dataclass

from sift.query import And, Field, Not, Or, Phrase, Prefix, Term, parse


@dataclass
class Point:
    """A class with an explicit __match_args__."""

    x: int
    y: int
    __match_args__ = ("y", "x")


def literal(command: str) -> str:
    """Match literals, an OR pattern and a wildcard."""
    match command:
        case "search":
            return "literal"
        case "stats" | "bench":
            return "or-pattern"
        case _:
            return "wildcard"


def sequence(items: list[int]) -> str:
    """Match sequences with captures and a star pattern."""
    match items:
        case []:
            return "empty"
        case [x]:
            return f"one item {x}"
        case [first, *rest] if first == 0:
            return f"starts with zero, {len(rest)} more"
        case [first, *_, last]:
            return f"first {first}, last {last}"
        case _:
            return "unreachable"


def mapping(event: dict[str, object]) -> str:
    """Match mappings: keys must exist, extra keys are fine."""
    match event:
        case {"type": "click", "pos": (x, y)}:
            return f"click at {x},{y}"
        case {"type": "key", "key": str() as key, **rest}:
            return f"key {key!r}, other keys {sorted(rest)}"
        case _:
            return "unknown event"


def classes(node: object) -> str:
    """Match classes by position and by keyword."""
    match node:
        case Point(0, 0):
            return "origin (positional: y, x)"
        case Point(x=x) if x < 0:
            return f"left half, x = {x}"
        case Term(text="kalman"):
            return "the word kalman"
        case Phrase((first, *_)):
            return f"phrase starting with {first!r}"
        case Not(Term(text) | Prefix(text)):
            return f"negated word or prefix {text!r}"
        case Field("tag" | "series" as name, value):
            return f"metadata field {name}: {value}"
        case And(Or() as left, right):
            return f"AND with an OR on the left: {left} / {right}"
        case int() | float() as number:
            return f"number {number}"
        case _:
            return "something else"


def main() -> None:
    """Run each matcher on a few inputs."""
    for command in ("search", "bench", "x"):
        print("literal", command, "->", literal(command))
    for items in ([], [7], [0, 1, 2], [1, 2, 3, 4]):
        print("sequence", items, "->", sequence(items))
    events = [
        {"type": "click", "pos": (3, 4)},
        {"type": "key", "key": "q", "mod": "ctrl", "repeat": 1},
        {"type": "click"},
    ]
    for event in events:
        print("mapping", event, "->", mapping(event))
    objects = [
        Point(0, 0),
        Point(-2, 5),
        Term("kalman"),
        parse('"device tree"'),
        Not(Term("latex")),
        parse("tag:Rust"),
        parse("(a OR b) c"),
        3.5,
        "text",
    ]
    for obj in objects:
        print("classes", obj, "->", classes(obj))


if __name__ == "__main__":
    main()
