"""Complete a Future by hand: callbacks, awaiting and failure."""

import asyncio
import threading


async def wait_for_it(future: asyncio.Future[int]) -> int:
    """Await a Future that somebody else will complete."""
    print("  waiter: awaiting, done =", future.done())
    value = await future
    print("  waiter: woke up with", value)
    return value * 2


async def result_demo() -> None:
    """A loop.call_later callback completes the Future."""
    print("-- set_result from a call_later callback")
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    waiter = asyncio.create_task(wait_for_it(future))
    await asyncio.sleep(0)  # let the waiter reach its await
    future.add_done_callback(lambda f: print("  callback: got", f.result()))
    loop.call_later(0.05, future.set_result, 21)
    print("  main: waiter returned", await waiter)
    print("  done =", future.done(), "result =", future.result())
    print("-- a Task is a Future: it has the same methods")
    print("  isinstance(waiter, Future):", isinstance(waiter, asyncio.Future))


async def exception_demo() -> None:
    """set_exception makes every awaiter raise."""
    print("-- set_exception")
    future: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    future.set_exception(ValueError("boom"))
    print("  exception():", repr(future.exception()))
    try:
        await future
    except ValueError as error:
        print("  await raised:", error)
    try:
        future.set_result(1)
    except asyncio.InvalidStateError:
        print("  a second set_result raises InvalidStateError")


async def cancel_demo() -> None:
    """cancel() ends a pending Future; awaiting it raises."""
    print("-- cancel")
    future: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    print("  cancel() returned", future.cancel())
    print("  cancelled():", future.cancelled(), "done():", future.done())
    try:
        await future
    except asyncio.CancelledError:
        print("  await raised CancelledError")
    print("  cancel() again returned", future.cancel())


async def thread_demo() -> None:
    """Another thread completes a Future through the loop."""
    print("-- set_result from another thread: call_soon_threadsafe")
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    threading.Thread(
        target=lambda: loop.call_soon_threadsafe(future.set_result, "hi")
    ).start()
    print("  awaited:", await future)


async def main() -> None:
    """Run the demos."""
    await result_demo()
    await exception_demo()
    await cancel_demo()
    await thread_demo()


if __name__ == "__main__":
    asyncio.run(main())
