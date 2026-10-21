"""Aliasing: one object, many names; shallow and deep copies."""

import copy


def main() -> None:
    """Show the classic traps."""
    a = [1, 2, 3]
    b = a
    b.append(4)
    print("alias:", a, a is b)

    grid = [[0] * 3] * 3
    grid[0][0] = 1
    print("[[0]*3]*3 :", grid, [id(r) == id(grid[0]) for r in grid])
    grid = [[0] * 3 for _ in range(3)]
    grid[0][0] = 1
    print("comprehension:", grid)

    inner = [1, 2]
    outer = [inner, "x"]
    shallow = copy.copy(outer)
    deep = copy.deepcopy(outer)
    inner.append(3)
    print("original:", outer)
    print("copy.copy:", shallow, shallow[0] is outer[0])
    print("deepcopy:", deep, deep[0] is outer[0])
    print("slice copy is shallow:", outer[:][0] is outer[0])

    # BAD: 默认值只在 def 执行时创建一次
    def append_to(
        item: int,
        bucket: list[int] = [],  # noqa: B006
    ) -> list[int]:
        bucket.append(item)
        return bucket

    print("mutable default:", append_to(1), append_to(2))


if __name__ == "__main__":
    main()
