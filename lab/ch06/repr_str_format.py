"""__repr__, __str__ and __format__ on a Posting-like class."""

import re

from sift.index import Posting, PostingList


class Hit:
    """A scored document with three different textual forms."""

    def __init__(self, doc_id: int, score: float) -> None:
        """Remember the document and its score."""
        self.doc_id = doc_id
        self.score = score

    def __repr__(self) -> str:
        """Return an unambiguous form that looks like the call."""
        return f"Hit(doc_id={self.doc_id}, score={self.score})"

    def __str__(self) -> str:
        """Return the form meant for a person."""
        return f"doc {self.doc_id} ({self.score:.2f})"

    def __format__(self, spec: str) -> str:
        """Format the score with spec, e.g. ``{hit:8.1f}``."""
        if not spec:
            return str(self)
        return f"doc {self.doc_id} {format(self.score, spec)}"


class Bare:
    """No __repr__ at all: the inherited object.__repr__ is used."""


def main() -> None:
    """Show where each of the three hooks is called."""
    hit = Hit(7, 3.14159)
    print("print(hit):     ", hit)
    print("repr(hit):      ", repr(hit))
    print("str(hit):       ", str(hit))
    print("f'{hit}':       ", f"{hit}")
    print("f'{hit:8.1f}':  ", f"{hit:8.1f}")
    print("f'{hit!r}':     ", f"{hit!r}")
    print("in a list:      ", [hit, hit])
    # The default repr holds a memory address; mask it for a stable run.
    print("Bare():         ", re.sub(r"0x[0-9a-f]+", "0x...", repr(Bare())))
    print("Posting:        ", Posting(3, (0, 5, 9)))
    print("PostingList:    ", PostingList([Posting(3, (0,))]))
    # str() falls back to repr() when only __repr__ is defined.
    print("str(Posting):   ", str(Posting(3, (0,))))
    # The repr round-trips: eval rebuilds an equal object.
    p = Posting(3, (0, 5, 9))
    print("eval(repr(p)) == p:", eval(repr(p)) == p)


if __name__ == "__main__":
    main()
