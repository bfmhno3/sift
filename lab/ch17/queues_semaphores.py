"""Queues and synchronization primitives for tasks."""

import asyncio


async def producer(queue: asyncio.Queue[int], count: int) -> None:
    """Put count items; put() waits when the queue is full."""
    for i in range(count):
        await queue.put(i)
    queue.shutdown()  # new in 3.13: consumers see QueueShutDown


async def consumer(
    name: str, queue: asyncio.Queue[int], seen: dict[str, list[int]]
) -> None:
    """Take items until the queue is shut down and empty."""
    while True:
        try:
            item = await queue.get()
        except asyncio.QueueShutDown:
            return
        await asyncio.sleep(0.01)
        seen[name].append(item)
        queue.task_done()


async def queue_demo() -> None:
    """One producer, three consumers, a queue of at most 2."""
    print("-- Queue(maxsize=2): backpressure on the producer")
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=2)
    seen: dict[str, list[int]] = {n: [] for n in "abc"}
    async with asyncio.TaskGroup() as group:
        group.create_task(producer(queue, 9))
        for name in seen:
            group.create_task(consumer(name, queue, seen))
    for name, items in seen.items():
        print(f"  consumer {name} took {items}")
    print(
        "  all 9 taken once:", sorted(sum(seen.values(), [])) == list(range(9))
    )


async def semaphore_demo() -> None:
    """A semaphore caps how many tasks are inside at once."""
    print("-- Semaphore(3) around 10 jobs")
    gate = asyncio.Semaphore(3)
    inside = 0
    peak = 0

    async def job() -> None:
        nonlocal inside, peak
        async with gate:
            inside += 1
            peak = max(peak, inside)
            await asyncio.sleep(0.02)
            inside -= 1

    async with asyncio.TaskGroup() as group:
        for _ in range(10):
            group.create_task(job())
    print("  most tasks inside at once:", peak)


async def lock_event_demo() -> None:
    """Show a Lock around a read-modify-write, and an Event."""
    print("-- Lock around a read-modify-write that awaits")
    counter = 0
    lock = asyncio.Lock()

    async def bump(use_lock: bool) -> None:
        nonlocal counter
        if use_lock:
            async with lock:
                value = counter
                await asyncio.sleep(0)
                counter = value + 1
        else:
            value = counter
            await asyncio.sleep(0)
            counter = value + 1

    for use_lock in (False, True):
        counter = 0
        async with asyncio.TaskGroup() as group:
            for _ in range(100):
                group.create_task(bump(use_lock))
        print(f"  lock={use_lock!s:<5} counter = {counter} of 100")
    print("-- Event: one task waits for a signal")
    ready = asyncio.Event()

    async def waiter() -> str:
        await ready.wait()
        return "released"

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0.01)
    print("  before set: done =", task.done())
    ready.set()
    print("  after set:", await task)


async def main() -> None:
    """Run the demos."""
    await queue_demo()
    await semaphore_demo()
    await lock_event_demo()


if __name__ == "__main__":
    asyncio.run(main())
