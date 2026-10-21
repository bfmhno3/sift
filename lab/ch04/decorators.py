"""Decorators: plain, with arguments, stacked, class-based, wraps."""

import functools


def plain(fn):
    """Log each call (no functools.wraps, on purpose)."""

    def wrapper(*args, **kwargs):
        print(f"plain: calling {fn.__name__}")
        return fn(*args, **kwargs)

    return wrapper


def wrapped(fn):
    """Log each call, keeping the metadata of fn."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"wrapped: calling {fn.__name__}")
        return fn(*args, **kwargs)

    return wrapper


def repeat(times):
    """Return a decorator that calls the function times times."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = None
            for _ in range(times):
                result = fn(*args, **kwargs)
            return result

        return wrapper

    return decorator


def tag(name):
    """Return a decorator that wraps the result in <name>...</name>."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return f"<{name}>{fn(*args, **kwargs)}</{name}>"

        return wrapper

    return decorator


class CountCalls:
    """Class-based decorator: the instance is the wrapper."""

    def __init__(self, fn):
        functools.update_wrapper(self, fn)
        self.fn = fn
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.fn(*args, **kwargs)


@plain
def f_plain(x):
    """Docstring of f_plain."""
    return x


@wrapped
def f_wrapped(x):
    """Docstring of f_wrapped."""
    return x


@repeat(3)
def hello():
    """Print a greeting."""
    print("hello")


@tag("b")
@tag("i")
def text():
    """Return a word."""
    return "sift"


@CountCalls
def square(x):
    """Return x squared."""
    return x * x


def main() -> None:
    """Show each decorator and what wraps preserves."""
    f_plain(1)
    f_wrapped(1)
    for fn in (f_plain, f_wrapped):
        print(fn.__name__, repr(fn.__doc__), hasattr(fn, "__wrapped__"))
    print(f_wrapped.__wrapped__(5))

    hello()

    # 叠放顺序：离函数最近的装饰器最先应用，所以最先包住结果
    print(text())
    print(text.__name__)

    square(3)
    square(4)
    print(square.calls, square.__name__, square(5))

    # 装饰器语法只是赋值：f = deco(f)
    def late(x):
        return x + 1

    late = wrapped(late)
    print(late(1), late.__name__)


if __name__ == "__main__":
    main()
