"""Show what a coroutine, an await and asyncio.run actually are."""

import asyncio
import inspect
from collections.abc import Coroutine, Generator


async def add(a: int, b: int) -> int:
    """Return a + b, after one trip through the event loop."""
    await asyncio.sleep(0)
    return a + b


async def total() -> int:
    """Await two coroutines one after the other."""
    return await add(1, 2) + await add(3, 4)


class Ready:
    """An awaitable: __await__ returns an iterator."""

    def __await__(self) -> Generator[None, None, int]:
        """Yield to the loop once, then finish with 42."""
        yield
        return 42


def drive(coro: Coroutine[None, None, int]) -> None:
    """Run a coroutine by hand, the way an event loop does."""
    steps = 0
    try:
        while True:
            coro.send(None)
            steps += 1
    except StopIteration as stop:
        print(f"  finished after {steps} suspension(s): {stop.value}")


def main() -> None:
    """Call, inspect, drive and run coroutines."""
    coro = add(1, 2)
    print("calling add(1, 2) returns:", type(coro).__name__)
    print("iscoroutine:", inspect.iscoroutine(coro))
    print("state:", inspect.getcoroutinestate(coro))
    print("nothing ran yet; drive it by hand:")
    drive(coro)
    print("state:", inspect.getcoroutinestate(coro))
    print("a custom awaitable, driven by hand:")

    async def use_ready() -> int:
        return await Ready()

    drive(use_ready())
    print("asyncio.run(total()):", asyncio.run(total()))
    print("-- await only works inside async def")
    try:
        compile("await add(1, 2)", "<top>", "exec")
    except SyntaxError as error:
        print("SyntaxError:", error.msg)


if __name__ == "__main__":
    main()
