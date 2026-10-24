"""Forget an await: the coroutine never runs, and Python warns."""

import asyncio
import gc
import time
import tracemalloc
import warnings


async def fetch() -> str:
    """Pretend to fetch something for a second."""
    await asyncio.sleep(1)
    return "data"


async def forgetful() -> float:
    """Call fetch() without await; return the seconds it took."""
    start = time.perf_counter()
    fetch()  # BAD: creates the coroutine and drops it
    return time.perf_counter() - start


def main() -> None:
    """Capture the RuntimeWarning that the dropped coroutine raises."""
    tracemalloc.start()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        elapsed = asyncio.run(forgetful())
        gc.collect()
    print(f"fetch() 'took' {elapsed * 1000:.3f} ms instead of 1000 ms")
    for item in caught:
        print(f"{item.category.__name__}: {item.message}")
    print("warnings captured:", len(caught))
    print("-- again, uncaught: the warning goes to stderr, with the")
    print("-- traceback of the line that created the coroutine")
    asyncio.run(forgetful())
    gc.collect()
    tracemalloc.stop()


if __name__ == "__main__":
    main()
