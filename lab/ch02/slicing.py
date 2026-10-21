"""Indexing, slicing and strides on str; str is immutable."""


def main() -> None:
    """Slice a string in every way the syntax allows."""
    s = "Python 与 Unicode"
    print(s[0], s[-1], s[7], s[:6], s[7:], s[::2], s[::-1])
    print(s[2:100], repr(s[100:]), s[-7:-3])
    cut = slice(0, 6)
    print(s[cut], cut.indices(len(s)))
    try:
        s[0] = "J"  # type: ignore[index]
    except TypeError as exc:
        print("TypeError:", exc)
    t = "J" + s[1:]
    print(t, s)
    emoji = "a😀b"
    print(len(emoji), emoji[1], emoji.encode()[1:2])
    flag = "\U0001f1e8\U0001f1f3"
    print(len(flag), flag)


if __name__ == "__main__":
    main()
