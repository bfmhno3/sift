"""Functions as values, key functions, map/filter vs comprehensions."""

from operator import itemgetter


def shout(s: str) -> str:
    """Return s in upper case with an exclamation mark."""
    return s.upper() + "!"


def apply(fn, value):
    """Call fn on value."""
    return fn(value)


def main() -> None:
    """Pass functions around."""
    handlers = {"shout": shout, "len": len, "rev": lambda s: s[::-1]}
    for name, fn in handlers.items():
        print(name, apply(fn, "sift"))
    print(type(shout), shout.__name__, callable(shout))

    words = ["tea", "Bicycle", "rust", "PID", "compiler"]
    print(sorted(words))
    print(sorted(words, key=str.lower))
    print(sorted(words, key=len))
    print(sorted(words, key=lambda w: (len(w), w)))
    print(max(words, key=len), min(words, key=len))
    pairs = [("tea", 3), ("bike", 1), ("rust", 2)]
    print(sorted(pairs, key=itemgetter(1)))

    nums = range(10)
    print(list(map(lambda n: n * n, nums)))
    print([n * n for n in nums])
    print(list(filter(lambda n: n % 2 == 0, nums)))
    print([n for n in nums if n % 2 == 0])
    # 已有具名函数时 map 更短；要写 lambda 时推导式更清楚
    print(list(map(str.strip, [" a ", "b  "])))
    print(list(map(pow, [2, 3], [3, 2], strict=True)))
    print(map(len, words))


if __name__ == "__main__":
    main()
