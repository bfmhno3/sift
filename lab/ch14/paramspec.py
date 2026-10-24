"""ParamSpec and Concatenate: decorators that keep the signature."""

import functools
import logging
import time
from collections.abc import Callable
from typing import Concatenate

from sift.util import timed

log = logging.getLogger("sift.lab")


def with_clock[**P, R](
    fn: Callable[P, R],
) -> Callable[P, tuple[R, float]]:
    """Return a function that gives (result, seconds).

    The result type changes, the parameters (P) do not.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> tuple[R, float]:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, time.perf_counter() - start

    return wrapper


def with_logger[**P, R](
    fn: Callable[Concatenate[logging.Logger, P], R],
) -> Callable[P, R]:
    """Inject a logger as the first argument and hide it.

    Concatenate adds one parameter in front of P: fn takes
    (Logger, *P), the decorated function takes just P.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(log, *args, **kwargs)

    return wrapper


@timed
def add(a: int, b: int = 0) -> int:
    """Return a + b; timed keeps this exact signature."""
    return a + b


@with_clock
def scale(value: int, factor: int = 2) -> int:
    """Return value * factor."""
    return value * factor


@with_logger
def describe(logger: logging.Logger, name: str, *, upper: bool = False) -> str:
    """Return name, upper-cased if asked; logger is injected."""
    logger.debug("describe %s", name)
    return name.upper() if upper else name


def main() -> None:
    """Call the three decorated functions."""
    print(add(1, b=2))
    value, seconds = scale(21, factor=2)
    print(value, seconds >= 0)
    print(describe("sift", upper=True))


if __name__ == "__main__":
    main()
