"""Small function helpers: a timing decorator and compose."""

import functools
import sys
import time
from collections.abc import Callable
from typing import Any


def timed[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Wrap fn so each call prints ``<qualname> took X ms`` to stderr."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            ms = (time.perf_counter() - start) * 1000
            print(f"{fn.__qualname__} took {ms:.1f} ms", file=sys.stderr)

    return wrapper


def compose(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Return a function that applies fns left to right.

    ``compose(f, g, h)(x)`` is ``h(g(f(x)))``. With no functions it
    returns its argument unchanged.
    """

    def composed(value: Any) -> Any:
        for fn in fns:
            value = fn(value)
        return value

    return composed
