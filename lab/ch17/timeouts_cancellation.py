"""Timeouts and cancellation: CancelledError is how a task stops."""

import asyncio


async def slow(name: str, seconds: float = 1.0) -> str:
    """Sleep for seconds, and report if cancelled on the way."""
    try:
        await asyncio.sleep(seconds)
        return f"{name} finished"
    except asyncio.CancelledError:
        print(f"    {name}: CancelledError raised at the await")
        raise  # always re-raise, or the cancel is swallowed
    finally:
        print(f"    {name}: cleanup runs")


async def timeout_demo() -> None:
    """asyncio.timeout cancels the block, then raises TimeoutError."""
    print("-- asyncio.timeout(0.1) around a 1 s sleep")
    try:
        async with asyncio.timeout(0.1):
            await slow("job")
    except TimeoutError:
        print("  TimeoutError, the block was cancelled")
    print("-- wait_for is the one-call form")
    try:
        await asyncio.wait_for(slow("job2"), timeout=0.1)
    except TimeoutError:
        print("  TimeoutError")


async def cancel_demo() -> None:
    """task.cancel() asks; the task decides when it stops."""
    print("-- task.cancel()")
    task = asyncio.create_task(slow("victim"))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print(
            "  await task raised CancelledError, cancelled():",
            task.cancelled(),
        )
    print("-- swallowing it is a bug: the task looks finished")

    async def swallow() -> str:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            return "swallowed"  # BAD
        return "not reached"

    task = asyncio.create_task(swallow())
    await asyncio.sleep(0.01)
    task.cancel()
    print("  result:", await task, "cancelled():", task.cancelled())


async def shield_demo() -> None:
    """shield lets the inner task survive a cancelled waiter."""
    print("-- shield: the waiter is cancelled, the work is not")
    inner = asyncio.create_task(slow("inner", 0.2))

    async def guarded() -> str:
        return await asyncio.shield(inner)

    waiter = asyncio.create_task(guarded())
    await asyncio.sleep(0.05)
    waiter.cancel()
    try:
        await waiter
    except asyncio.CancelledError:
        print("  waiter cancelled; inner done:", inner.done())
    print(" ", await inner)


async def main() -> None:
    """Run the demos."""
    await timeout_demo()
    await cancel_demo()
    await shield_demo()


if __name__ == "__main__":
    asyncio.run(main())
