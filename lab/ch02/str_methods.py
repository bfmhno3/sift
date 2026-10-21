"""Everyday str methods, interning and the cost of +=."""

import sys
import timeit


def concat(n: int) -> str:
    """Build a string with +=."""
    out = ""
    for i in range(n):
        out += str(i)
    return out


def joined(n: int) -> str:
    """Build the same string with join."""
    return "".join([str(i) for i in range(n)])


def main() -> None:
    """Tour the methods, then time += against join."""
    line = "  key = value = more  "
    print(line.strip().split(" = "))
    print(line.strip().split(" = ", 1), line.split())
    print("key=value".partition("="), "a.b.c".rpartition("."))
    print(",".join(["a", "b", "c"]), "ab".center(6, "*"))
    print("Index.md".startswith(("Index", "README")))
    print("a.md".endswith((".md", ".txt")), "x".zfill(4))
    print("a-b_c".translate(str.maketrans("-_", "  ")))
    print("hello".translate(str.maketrans("", "", "l")))
    print("a b a".replace("a", "x", 1), "a\tb\n".expandtabs(4))
    print("Straße".title(), "éa".isalpha(), "١٢٣".isdigit())
    csv, spaced = "a,b,,c", "a b  c"
    print(csv.split(","), spaced.split(" "), spaced.split())
    print("line1\nline2\r\nline3".splitlines())

    a = "".join(["sif", "t"])
    b = "".join(["sif", "t"])
    print(a == b, a is b, sys.intern(a) is sys.intern(b))
    c, d = "sift", "sift"  # 同一个编译单元里的字面量被驻留
    print(c is d)

    n = 100_000
    t_add = min(timeit.repeat(lambda: concat(n), number=1, repeat=5))
    t_join = min(timeit.repeat(lambda: joined(n), number=1, repeat=5))
    print(f"+= : {t_add * 1000:.2f} ms for {n} pieces")
    print(f"join: {t_join * 1000:.2f} ms for {n} pieces")
    print(f"ratio += / join: {t_add / t_join:.2f}")


if __name__ == "__main__":
    main()
