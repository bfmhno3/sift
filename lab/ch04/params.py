"""Parameter kinds: /, *, defaults, *args, **kwargs, unpacking."""


def positional_only(a, b, /, c):
    """Take a and b by position only; c either way."""
    return a, b, c


def keyword_only(a, *, sep=" ", end="!"):
    """Take sep and end by keyword only."""
    return f"{a}{sep}{end}"


def everything(a, b=2, /, c=3, *args, d, e=5, **kwargs):
    """Use every parameter kind at once."""
    return a, b, c, args, d, e, kwargs


def search(query, *, limit=10, **filters):
    """Collect extra keyword arguments as filters."""
    return query, limit, filters


def main() -> None:
    """Call the functions in every legal way."""
    print(positional_only(1, 2, 3), positional_only(1, 2, c=3))
    print(keyword_only("hi"), keyword_only("hi", sep="-", end="?"))
    print(everything(1, d=4))
    print(everything(1, 9, 8, 7, 6, d=4, x=0))
    print(search("kalman", limit=3, tag="Rust", year=2026))

    # 调用处解包：* 展开序列，** 展开映射
    args = (1, 2)
    kwargs = {"c": 3}
    print(positional_only(*args, **kwargs))
    print(everything(*"abc", d=1, **{"z": 26}))
    merged = {**{"limit": 5}, **{"limit": 7, "tag": "c"}}
    print(search("pid", **merged))

    # 函数是对象：默认值和签名都存在对象上
    print(everything.__defaults__, everything.__kwdefaults__)
    print(everything.__code__.co_varnames[:7])
    print(
        everything.__code__.co_posonlyargcount,
        everything.__code__.co_kwonlyargcount,
    )


if __name__ == "__main__":
    main()
