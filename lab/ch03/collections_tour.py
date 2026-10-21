"""collections: Counter, defaultdict, deque, namedtuple, ChainMap."""

from collections import (
    ChainMap,
    Counter,
    OrderedDict,
    defaultdict,
    deque,
    namedtuple,
)


def main() -> None:
    """Print one example per container."""
    counts = Counter("abracadabra")
    print(counts.most_common(3), counts["z"])
    counts.update("aaa")
    print(counts + Counter("bb"), counts - Counter("a" * 10))

    groups: defaultdict[int, list[str]] = defaultdict(list)
    for word in ["tea", "bike", "rust", "pid", "gdb"]:
        groups[len(word)].append(word)
    print(dict(groups))

    window: deque[int] = deque(maxlen=3)
    for i in range(6):
        window.append(i)
    print("deque(maxlen=3):", window)
    window.rotate(1)
    print("rotate(1):", window)

    Hit = namedtuple("Hit", ["doc_id", "score"])
    hit = Hit(7, 1.5)
    print(hit, hit.doc_id, hit._replace(score=2.0), hit._asdict())

    defaults = {"k1": 1.2, "b": 0.75}
    overrides = {"b": 0.5}
    config = ChainMap(overrides, defaults)
    print(config["b"], config["k1"], list(config.maps))

    lru: OrderedDict[str, int] = OrderedDict(a=1, b=2, c=3)
    lru.move_to_end("a")
    print("move_to_end:", list(lru))
    lru.popitem(last=False)
    print("popitem(last=False):", list(lru))


if __name__ == "__main__":
    main()
