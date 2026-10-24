"""Async generators, async for, async with, asynccontextmanager."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager


async def ticker(count: int, delay: float) -> AsyncIterator[int]:
    """Yield 0 to count - 1, pausing delay seconds before each."""
    try:
        for i in range(count):
            await asyncio.sleep(delay)
            yield i
    finally:
        print("    ticker closed")


class Countdown:
    """An async iterator class: __aiter__ and __anext__."""

    def __init__(self, start: int) -> None:
        """Count down from start to 1."""
        self.value = start

    def __aiter__(self) -> Countdown:
        """Return self, like a sync iterator."""
        return self

    async def __anext__(self) -> int:
        """Return the next number after one trip to the loop."""
        await asyncio.sleep(0)
        if self.value == 0:
            raise StopAsyncIteration
        self.value -= 1
        return self.value + 1


class Connection:
    """An async context manager written with the two methods."""

    async def __aenter__(self) -> Connection:
        """Open (pretend to wait for the network)."""
        await asyncio.sleep(0.01)
        print("    connection open")
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close, also when the block raised."""
        await asyncio.sleep(0.01)
        print("    connection closed")


@asynccontextmanager
async def transaction(name: str) -> AsyncIterator[str]:
    """The same idea as a generator: code before and after yield."""
    print(f"    begin {name}")
    try:
        yield name
    except ValueError:
        print(f"    rollback {name}")
        raise
    else:
        print(f"    commit {name}")


async def main() -> None:
    """Use each of them."""
    print("-- async for over an async generator")
    async for number in ticker(3, 0.01):
        print("   ", number)
    print("-- break, then aclosing() closes the generator")
    async with aclosing(ticker(5, 0.01)) as stream:
        async for number in stream:
            if number == 1:
                break
    print("-- an async iterator class")
    print("   ", [n async for n in Countdown(3)])
    print("-- async comprehension with a condition, and anext()")
    print("   ", [n async for n in ticker(6, 0) if n % 2 == 0])
    stream = ticker(2, 0)
    print("    anext:", await anext(stream), await anext(stream))
    await stream.aclose()
    print("-- async with")
    async with Connection():
        print("    using it")
    print("-- asynccontextmanager, commit and rollback")
    async with transaction("t1"):
        pass
    try:
        async with transaction("t2"):
            raise ValueError("boom")
    except ValueError:
        print("    error reached the caller")


if __name__ == "__main__":
    asyncio.run(main())
