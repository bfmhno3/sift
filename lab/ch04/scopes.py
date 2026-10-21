"""LEGB name lookup, global and nonlocal."""

x = "global"
counter = 0


def show_legb() -> None:
    """Resolve x through Local, Enclosing, Global and Built-in."""
    x = "enclosing"

    def inner() -> None:
        x = "local"
        print("L:", x)

    def inner_enclosing() -> None:
        print("E:", x)

    inner()
    inner_enclosing()


def show_global() -> None:
    """Read the global x, and len from the built-in scope."""
    print("G:", x)
    print("B:", len)


def bump_global() -> None:
    """Rebind a module-level name; needs the global declaration."""
    global counter
    counter += 1


def make_counter():
    """Return a function that counts calls in an enclosing variable."""
    count = 0

    def tick() -> int:
        nonlocal count
        count += 1
        return count

    return tick


def main() -> None:
    """Exercise each rule."""
    show_legb()
    show_global()
    bump_global()
    bump_global()
    print("counter:", counter)
    tick = make_counter()
    print(tick(), tick(), tick())
    other = make_counter()
    print(other(), tick())
    # 推导式有自己的作用域，循环变量不会泄漏
    squares = [n * n for n in range(3)]
    print(squares, "n" in globals())
    # 这些名字在编译期就分好了类
    print(show_legb.__code__.co_varnames, tick.__code__.co_freevars)


if __name__ == "__main__":
    main()
