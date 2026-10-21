"""operator: functions for the built-in operators."""

import operator
from functools import reduce
from operator import attrgetter, itemgetter, methodcaller


def main() -> None:
    """Replace small lambdas with operator functions."""
    print(operator.add(2, 3), operator.mul(4, 5), operator.lt(1, 2))
    print(reduce(operator.mul, range(1, 6)))

    rows = [("tea", 3), ("bike", 1), ("rust", 2)]
    print(sorted(rows, key=itemgetter(1)))
    print(itemgetter(0, 1)(["a", "b", "c"]))
    print(itemgetter("x", "y")({"x": 1, "y": 2, "z": 3}))

    class Doc:
        def __init__(self, title: str, size: int) -> None:
            self.title = title
            self.size = size

        def __repr__(self) -> str:
            return f"Doc({self.title!r}, {self.size})"

    docs = [Doc("b", 2), Doc("a", 9), Doc("c", 5)]
    print(sorted(docs, key=attrgetter("size")))
    print(max(docs, key=attrgetter("size")))
    print(attrgetter("title", "size")(docs[0]))

    print(methodcaller("upper")("sift"))
    print(methodcaller("split", ",")("a,b,c"))
    print(list(map(methodcaller("strip"), [" a ", "b "])))

    # operator.itemgetter 比 lambda 快一点，也更能说明意图
    print(sorted(rows, key=lambda r: r[1]) == sorted(rows, key=itemgetter(1)))


if __name__ == "__main__":
    main()
