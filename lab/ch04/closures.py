"""Closures: __closure__, cells, late binding and the i=i fix."""


def make_multiplier(factor):
    """Return a function that multiplies by factor."""

    def multiply(x):
        return x * factor

    return multiply


def main() -> None:
    """Inspect cells and reproduce the late-binding trap."""
    double = make_multiplier(2)
    print(double.__closure__)
    print(double.__code__.co_freevars)
    print(double.__closure__[0].cell_contents)
    print(double(21))

    # BAD: 三个 lambda 共享同一个 cell，循环结束时 i 是 2
    late = [lambda: i for i in range(3)]  # noqa: B023
    print([f() for f in late])
    print([f.__closure__[0].cell_contents for f in late])
    print(late[0].__closure__[0] is late[1].__closure__[0])

    # 修复：用默认参数在定义时把当前值绑定进去
    bound = [lambda i=i: i for i in range(3)]
    print([f() for f in bound])
    print(bound[0].__closure__, bound[0].__defaults__)

    # 另一种修复：每次调用工厂函数，得到各自的 cell
    made = [make_multiplier(k) for k in range(3)]
    print([f(10) for f in made])

    # cell 是可变的：外层改了，内层看得到
    def outer():
        value = 1

        def read():
            return value

        value = 2
        return read

    print(outer()())


if __name__ == "__main__":
    main()
