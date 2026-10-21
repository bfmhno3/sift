"""__len__ and __getitem__ make for, in, reversed and bool work."""

from sift.index import Posting, PostingList


class Countdown:
    """Only __len__ and __getitem__: no __iter__, no __contains__."""

    def __len__(self) -> int:
        """Return the number of items."""
        return 3

    def __getitem__(self, i: int) -> int:
        """Return 3 - i, raising IndexError past the end."""
        if not 0 <= i < 3:
            raise IndexError(i)
        return 3 - i


class Basket:
    """Empty baskets are falsy through __len__ ... or __bool__."""

    def __init__(self, items: list[str]) -> None:
        """Keep the items."""
        self.items = items

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self.items)


class Switch:
    """__bool__ wins over __len__ when both exist."""

    def __len__(self) -> int:
        """Pretend to be empty."""
        return 0

    def __bool__(self) -> bool:
        """Always true."""
        return True


def main() -> None:
    """Show the protocols on Countdown and on PostingList."""
    c = Countdown()
    print("len:", len(c))
    print("for:", [x for x in c])
    print("in:", 2 in c, 7 in c)
    print("reversed:", list(reversed(c)))
    print("list(c):", list(c))
    print("hasattr __iter__:", hasattr(c, "__iter__"))
    print("iter(c):", type(iter(c)).__name__)

    pl = PostingList([Posting(2, (0,)), Posting(5, (1, 3))])
    print("PostingList len:", len(pl))
    print("pl[1]:", pl[1])
    print("5 in pl, 3 in pl:", 5 in pl, 3 in pl)
    print("for doc ids:", [p.doc_id for p in pl])
    print("bool(pl), bool(PostingList()):", bool(pl), bool(PostingList()))

    print("bool(Basket([])), bool(Basket(['a'])):")
    print("  ", bool(Basket([])), bool(Basket(["a"])))
    print("len(Switch()), bool(Switch()):", len(Switch()), bool(Switch()))


if __name__ == "__main__":
    main()
