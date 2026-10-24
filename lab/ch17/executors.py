"""Run blocking code from a coroutine: executors and contextvars."""

import asyncio
import contextvars
import os
import sys
import time
from collections.abc import Awaitable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def pid_and_square(n: int) -> tuple[int, int]:
    """Run in a worker process: return its pid and n * n."""
    return os.getpid(), n * n


def read_request_id() -> str:
    """Return the request id this thread sees."""
    return request_id.get()


async def timed(label: str, *jobs: Awaitable[object]) -> None:
    """Await the jobs together; print the rounded seconds."""
    start = time.perf_counter()
    await asyncio.gather(*jobs)
    print(f"  {label}: {time.perf_counter() - start:.1f} s")


async def thread_demo() -> None:
    """Four sleeps of 0.2 s on different thread pools."""
    loop = asyncio.get_running_loop()
    print("-- four time.sleep(0.2) calls")
    await timed(
        "run_in_executor(None, ...)  default pool",
        *(loop.run_in_executor(None, time.sleep, 0.2) for _ in range(4)),
    )
    with ThreadPoolExecutor(2) as pool:
        await timed(
            "run_in_executor(pool of 2, ...)",
            *(loop.run_in_executor(pool, time.sleep, 0.2) for _ in range(4)),
        )
    await timed(
        "asyncio.to_thread (the default pool again)",
        *(asyncio.to_thread(time.sleep, 0.2) for _ in range(4)),
    )


async def process_demo() -> None:
    """CPU work goes to another process, not another thread."""
    loop = asyncio.get_running_loop()
    print("-- ProcessPoolExecutor(2)")
    with ProcessPoolExecutor(2) as pool:
        answers = await asyncio.gather(
            *(loop.run_in_executor(pool, pid_and_square, n) for n in (3, 4))
        )
    print("  squares:", [square for _, square in answers])
    print(
        "  ran in another process:", all(p != os.getpid() for p, _ in answers)
    )


async def context_demo() -> None:
    """Which thread sees the ContextVar of the coroutine?"""
    loop = asyncio.get_running_loop()
    request_id.set("req-1")
    print("-- ContextVar set to 'req-1' before the call")
    print(
        "  run_in_executor sees:",
        await loop.run_in_executor(None, read_request_id),
    )
    print("  to_thread sees      :", await asyncio.to_thread(read_request_id))
    copied = contextvars.copy_context()
    print(
        "  run_in_executor(ctx.run, ...) sees:",
        await loop.run_in_executor(None, copied.run, read_request_id),
    )


async def main() -> None:
    """Run the demos and say which build ran them."""
    gil = sys._is_gil_enabled()
    inherit = sys.flags.thread_inherit_context
    print(f"python {sys.version.split()[0]}, GIL enabled: {gil}")
    print("sys.flags.thread_inherit_context:", inherit)
    # first: a pool thread is created by its first job and keeps the
    # context it was created with (or none) for every later job
    await context_demo()
    await thread_demo()
    await process_demo()


if __name__ == "__main__":
    asyncio.run(main())
