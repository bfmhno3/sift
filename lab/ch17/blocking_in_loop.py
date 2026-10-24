"""Block the event loop with time.sleep and measure the stall."""

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable

BLOCK = 0.3  # seconds a coroutine holds the loop
BEAT = 0.01  # seconds between two heartbeats


async def heartbeat(gaps: list[float]) -> None:
    """Record how long each sleep(BEAT) really took."""
    loop = asyncio.get_running_loop()
    last = loop.time()
    while True:
        await asyncio.sleep(BEAT)
        now = loop.time()
        gaps.append(now - last)
        last = now


async def blocking() -> None:
    """BAD: time.sleep holds the thread, so the loop cannot run."""
    time.sleep(BLOCK)


async def threaded() -> None:
    """Move the blocking call to a worker thread."""
    await asyncio.to_thread(time.sleep, BLOCK)


async def stall(work: Callable[[], Awaitable[None]]) -> float:
    """Run work next to a heartbeat; return the longest gap in ms."""
    gaps: list[float] = []
    beat = asyncio.create_task(heartbeat(gaps))
    await asyncio.sleep(0.05)  # let the heartbeat settle
    await work()
    await asyncio.sleep(0.05)
    beat.cancel()
    return max(gaps) * 1000


async def compare() -> None:
    """Print the loop stall of the two versions."""
    bad = await stall(blocking)
    good = await stall(threaded)
    print(f"heartbeat every {BEAT * 1000:.0f} ms,", end=" ")
    print(f"work blocks {BLOCK * 1000:.0f} ms")
    print(f"time.sleep in a coroutine: longest gap {bad:6.1f} ms")
    print(f"asyncio.to_thread        : longest gap {good:6.1f} ms")


def debug_child() -> None:
    """Run the blocking coroutine; PYTHONASYNCIODEBUG=1 reports it."""
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(blocking())


def debug_demo() -> None:
    """Re-run this file with PYTHONASYNCIODEBUG=1; show its warning."""
    env = dict(os.environ, PYTHONASYNCIODEBUG="1")
    done = subprocess.run(
        [sys.executable, __file__, "--debug-child"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    print("-- PYTHONASYNCIODEBUG=1 names the slow callback:")
    for line in done.stderr.splitlines():
        if "took" in line:
            print(" ", line.replace(os.getcwd() + "/", ""))


def main() -> None:
    """Measure the stall, then show the debug-mode warning."""
    if sys.argv[1:] == ["--debug-child"]:
        debug_child()
        return
    asyncio.run(compare())
    debug_demo()


if __name__ == "__main__":
    main()
