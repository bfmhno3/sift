"""A tour of itertools, plus the groupby and tee pitfalls."""

import itertools
from operator import itemgetter


def main() -> None:
    """Print one small example per tool."""
    parts = [["a", "b"], ["c"], [], ["d", "e"]]
    print("chain.from_iterable:", list(itertools.chain.from_iterable(parts)))
    print("chain:", list(itertools.chain("ab", range(2))))

    print("count:", list(itertools.islice(itertools.count(10, 5), 4)))
    print("islice:", list(itertools.islice("abcdefgh", 2, 7, 2)))
    print("cycle:", list(itertools.islice(itertools.cycle("xy"), 5)))
    print("repeat:", list(itertools.repeat("z", 3)))

    print("accumulate:", list(itertools.accumulate([1, 2, 3, 4])))
    print("accumulate max:", list(itertools.accumulate([3, 1, 4, 1, 5], max)))
    print("batched:", list(itertools.batched(range(7), 3, strict=False)))
    print("pairwise:", list(itertools.pairwise("abcd")))
    print("product:", list(itertools.product("ab", range(2))))
    print("permutations:", list(itertools.permutations("abc", 2)))
    print("combinations:", list(itertools.combinations("abc", 2)))
    print("takewhile:", list(itertools.takewhile(lambda n: n < 4, range(9))))
    print("dropwhile:", list(itertools.dropwhile(lambda n: n < 4, range(7))))
    print(
        "zip_longest:", list(itertools.zip_longest("ab", "xyz", fillvalue="-"))
    )

    # groupby only groups ADJACENT equal keys.
    rows = [("tea", 1), ("bike", 2), ("tea", 3), ("bike", 4), ("tea", 5)]
    print("groupby unsorted:")
    for key, group in itertools.groupby(rows, key=itemgetter(0)):
        print("  ", key, list(group))
    print("groupby sorted:")
    for key, group in itertools.groupby(
        sorted(rows, key=itemgetter(0)), key=itemgetter(0)
    ):
        print("  ", key, list(group))

    # A group is a view of the shared iterator: keep it and it is gone.
    kept = [group for _, group in itertools.groupby("aabbb")]
    print("groups kept past the loop:", [list(g) for g in kept])

    # tee: two independent iterators over one source.
    left, right = itertools.tee(iter(range(4)))
    print("tee:", list(left), list(right))
    source = iter(range(4))
    left, right = itertools.tee(source)
    print("tee, source also consumed:", list(source), list(left))

    print("zip strict ok:", list(zip("ab", [1, 2], strict=True)))


if __name__ == "__main__":
    main()
