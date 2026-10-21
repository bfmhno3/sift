"""functools: partial, lru_cache, cache, reduce, singledispatch."""

import functools
import time
from functools import cache, lru_cache, partial, reduce, singledispatch
from pathlib import Path


def fib_naive(n: int) -> int:
    """Return the n-th Fibonacci number, recomputing everything."""
    return n if n < 2 else fib_naive(n - 1) + fib_naive(n - 2)


@cache
def fib_cached(n: int) -> int:
    """Return the n-th Fibonacci number, remembering each result."""
    return n if n < 2 else fib_cached(n - 1) + fib_cached(n - 2)


@lru_cache(maxsize=2)
def square(n: int) -> int:
    """Return n squared; keep only the 2 most recent results."""
    return n * n


@singledispatch
def describe(obj) -> str:
    """Describe obj by its type; the default case."""
    return f"object {obj!r}"


@describe.register
def _(obj: int) -> str:
    return f"int with {obj.bit_length()} bits"


@describe.register
def _(obj: list) -> str:
    return f"list of {len(obj)} items"


@describe.register
def _(obj: Path) -> str:
    return f"path named {obj.name}"


def main() -> None:
    """Tour the module and time fib(30) both ways."""
    int16 = partial(int, base=16)
    print(int16("ff"), int16.func, int16.args, int16.keywords)

    for n in (1, 2, 1, 3, 1):
        square(n)
    print(square.cache_info())
    square.cache_clear()
    print(square.cache_info())

    print(reduce(lambda a, b: a * b, range(1, 6)))
    print(reduce(lambda a, b: a + b, [[1], [2, 3], [4]], []))
    print(reduce(max, [3, 9, 2], 0))

    for value in (7, [1, 2], Path("a/b.md"), 3.5):
        print(describe(value))
    print(sorted(t.__name__ for t in describe.registry))

    start = time.perf_counter()
    naive = fib_naive(30)
    t_naive = time.perf_counter() - start
    start = time.perf_counter()
    cached = fib_cached(30)
    t_cached = time.perf_counter() - start
    assert naive == cached
    print(f"fib(30) = {naive}")
    print(f"naive:  {t_naive * 1000:10.3f} ms")
    print(f"cached: {t_cached * 1000:10.3f} ms")
    print(f"speedup: {t_naive / t_cached:.0f}x")
    print(fib_cached.cache_info())
    print(functools.cache.__name__)


if __name__ == "__main__":
    main()
