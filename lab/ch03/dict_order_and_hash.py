"""dict keeps insertion order; hash() of ints, str and tuples."""

import os


def main() -> None:
    """Print ordering facts and hash values (str hashes vary by seed)."""
    print("PYTHONHASHSEED =", os.environ.get("PYTHONHASHSEED"))
    d = {"b": 1, "a": 2}
    d["c"] = 3
    del d["b"]
    d["b"] = 4
    print("insertion order:", list(d))
    print("equal dicts, other order:", {"x": 1, "y": 2} == {"y": 2, "x": 1})
    print("set order of small ints:", list({5, 3, 8, 1}))
    for n in (0, 1, 42, -1, -2, 2**61 - 1, 2**61):
        print(f"hash({n}) = {hash(n)}")
    print("hash(1.0) == hash(1):", hash(1.0) == hash(1))
    print("hash(True) == hash(1):", hash(True) == hash(1))
    print("hash('sift') =", hash("sift"))
    print("hash('') =", hash(""))
    print("hash((1, 2)) =", hash((1, 2)))
    print("hash(('a', 1)) =", hash(("a", 1)))
    print("hash(frozenset({1, 2})) =", hash(frozenset({1, 2})))
    words = ["tea", "bike", "rust", "kalman", "pid", "gdb"]
    print("set of str:", list(set(words)))


if __name__ == "__main__":
    main()
