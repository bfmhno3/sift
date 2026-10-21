"""The mutable default argument bug and the None idiom."""


# BAD: tags=[] is built once and shared by every call
def add_tag_bad(tag, tags=[]):  # noqa: B006
    """Append tag to tags and return it."""
    tags.append(tag)
    return tags


def add_tag(tag, tags=None):
    """Append tag to tags, creating a fresh list when none is given."""
    if tags is None:
        tags = []
    tags.append(tag)
    return tags


def main() -> None:
    """Call both versions twice."""
    print(add_tag_bad("a"), add_tag_bad("b"))
    print(add_tag_bad.__defaults__)
    print(add_tag("a"), add_tag("b"))
    print(add_tag.__defaults__)
    # 默认值在 def 执行时求值一次，之后一直挂在函数对象上


if __name__ == "__main__":
    main()
