"""Run coroutines concurrently: tasks, gather and TaskGroup."""

import asyncio


async def work(name: str, seconds: float, fail: bool = False) -> str:
    """Sleep, then return a result or raise."""
    try:
        await asyncio.sleep(seconds)
        if fail:
            raise ValueError(f"{name} failed")
        return f"{name} done"
    except asyncio.CancelledError:
        print(f"    {name} was cancelled")
        raise


async def create_task_demo() -> None:
    """Tasks start running at the next await; await collects them."""
    print("-- create_task: both run at once, 0.2 s in total")
    loop = asyncio.get_running_loop()
    start = loop.time()
    first = asyncio.create_task(work("a", 0.2))
    second = asyncio.create_task(work("b", 0.2))
    print(" ", await first, "and", await second)
    print(f"  elapsed {loop.time() - start:.2f} s")


async def gather_demo() -> None:
    """gather returns results in argument order."""
    print("-- gather: results in the order of the arguments")
    print(" ", await asyncio.gather(work("slow", 0.2), work("fast", 0.0)))
    print("-- gather(return_exceptions=True): errors become results")
    results = await asyncio.gather(
        work("a", 0.0),
        work("b", 0.0, fail=True),
        work("c", 0.1),
        return_exceptions=True,
    )
    for result in results:
        print("  ", repr(result))
    print("-- gather without it: first error raised, siblings run on")
    try:
        await asyncio.gather(work("x", 0.0, fail=True), work("y", 0.1))
    except ValueError as error:
        print("  raised", error)
    await asyncio.sleep(0.2)  # y finishes unobserved, never cancelled


async def taskgroup_demo() -> None:
    """A failing child cancels its siblings; errors come grouped."""
    print("-- TaskGroup: one failing child cancels the others")
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(work("ok", 0.3))
            group.create_task(work("bad", 0.05, fail=True))
            group.create_task(work("bad2", 0.05, fail=True))
    except* ValueError as errors:
        print("  ExceptionGroup:", errors.exceptions)
        print("  message:", errors.message)
    print("-- TaskGroup: all children done, results via .result()")
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(work(n, 0.0)) for n in "pq"]
    print(" ", [task.result() for task in tasks])


async def main() -> None:
    """Run the three demos."""
    await create_task_demo()
    await gather_demo()
    await taskgroup_demo()


if __name__ == "__main__":
    asyncio.run(main())
