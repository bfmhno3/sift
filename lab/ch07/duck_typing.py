"""Duck typing: use what an object does, not what it is."""

import os
from collections.abc import Iterable
from io import StringIO


class Shout:
    """Has write() like a file, but only collects upper-case text."""

    def __init__(self) -> None:
        """Start empty."""
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        """Keep text in upper case; return its length."""
        self.parts.append(text.upper())
        return len(text)


def dump(lines: Iterable[str], out) -> None:
    """Write every line to out: anything with write() will do."""
    for line in lines:
        out.write(line + "\n")


def total_length(items) -> int:
    """Sum len() of items: EAFP instead of an isinstance check."""
    total = 0
    for item in items:
        try:
            total += len(item)
        except TypeError:
            total += len(str(item))
    return total


def main() -> None:
    """Pass three unrelated objects to the same function."""
    words = ["kalman", "filter"]
    buffer = StringIO()
    shout = Shout()
    dump(words, buffer)
    dump(words, shout)
    print("StringIO:", repr(buffer.getvalue()))
    print("Shout   :", repr("".join(shout.parts)))
    with open(os.devnull, "w", encoding="utf-8") as sink:
        dump(words, sink)
    print("devnull : accepted too")
    print("total_length:", total_length(["ab", (1, 2, 3), 12345, {1: 2}]))
    try:
        dump(words, 42)
    except AttributeError as exc:
        print("AttributeError:", exc)


if __name__ == "__main__":
    main()
