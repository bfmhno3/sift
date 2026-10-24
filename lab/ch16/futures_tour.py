"""concurrent.futures: pools, as_completed, wait, cancel, errors."""

import os
import time
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from concurrent.futures.process import BrokenProcessPool


def nap(name: str, seconds: float) -> str:
    """Sleep, then return the name."""
    time.sleep(seconds)
    return name


def fail(n: int) -> int:
    """Raise for odd numbers."""
    if n % 2:
        raise ValueError(f"{n} is odd")
    return n


def square(n: int) -> int:
    """A function a process can run."""
    return n * n


def die(_: int) -> int:
    """Kill the worker process without raising."""
    os._exit(1)


def threads() -> None:
    """submit, map, as_completed, wait."""
    print("-- ThreadPoolExecutor: submit, map")
    with ThreadPoolExecutor(3) as pool:
        future = pool.submit(square, 12)
        print("  submit(square, 12).result():", future.result())
        print(
            "  map keeps the input order  :", list(pool.map(square, range(6)))
        )
    print("-- as_completed yields in the order of finishing")
    with ThreadPoolExecutor(3) as pool:
        futures = {
            pool.submit(nap, name, secs): name
            for name, secs in (("slow", 0.6), ("fast", 0.1), ("mid", 0.35))
        }
        print("  ", [futures[f] for f in as_completed(futures)])
    print("-- wait(return_when=FIRST_COMPLETED)")
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(nap, "a", 0.5)
        b = pool.submit(nap, "b", 0.05)
        done, pending = wait([a, b], return_when=FIRST_COMPLETED)
        print("  done:", [f.result() for f in done], "pending:", len(pending))
        done, pending = wait([a, b])
        print("  after wait(all): done", len(done), "pending", len(pending))


def cancelling() -> None:
    """Only queued futures can be cancelled."""
    print("-- cancel()")
    with ThreadPoolExecutor(1) as pool:
        running = pool.submit(nap, "running", 0.3)
        queued = [pool.submit(nap, f"q{i}", 0.01) for i in range(3)]
        time.sleep(0.05)
        print("  running.cancel():", running.cancel(), running.running())
        print("  queued.cancel() :", [f.cancel() for f in queued])
        print("  cancelled()     :", [f.cancelled() for f in queued])
    print("-- shutdown(cancel_futures=True)")
    pool = ThreadPoolExecutor(1)
    first = pool.submit(nap, "first", 0.2)
    rest = [pool.submit(nap, f"r{i}", 0.01) for i in range(3)]
    time.sleep(0.05)
    pool.shutdown(cancel_futures=True)
    print(
        "  first:",
        first.result(),
        "| rest cancelled:",
        [f.cancelled() for f in rest],
    )


def errors() -> None:
    """Exceptions travel through the future."""
    print("-- exceptions")
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(fail, n) for n in range(4)]
        for n, future in enumerate(futures):
            error = future.exception()
            print(f"  fail({n}): {error!r}" if error else f"  fail({n}): ok")
        try:
            futures[1].result()
        except ValueError as error:
            print("  result() re-raises:", error)
        try:
            list(pool.map(fail, [2, 3, 4]))
        except ValueError as error:
            print("  map raises at the failing item:", error)
        slow = pool.submit(nap, "slow", 0.3)
        try:
            slow.result(timeout=0.05)
        except TimeoutError:
            print("  result(timeout=0.05): TimeoutError (the job goes on)")
        seen: list[str] = []
        slow.add_done_callback(lambda f: seen.append(f.result()))
        slow.result()
        print("  done callback ran:", seen)


def processes() -> None:
    """The same API over processes; errors are pickled back."""
    print("-- ProcessPoolExecutor")
    with ProcessPoolExecutor(2) as pool:
        print("  map(square):", list(pool.map(square, range(6))))
        error = pool.submit(fail, 3).exception()
        print("  remote error:", repr(error))
        print(
            "  its cause is a text traceback:", type(error.__cause__).__name__
        )
    with ProcessPoolExecutor(2) as pool:
        try:
            pool.submit(die, 0).result()
        except BrokenProcessPool as broken:
            print("  worker died ->", type(broken).__name__)
        try:
            pool.submit(square, 2)
        except BrokenProcessPool:
            print("  the pool is broken for every later submit")


def main() -> None:
    """Run every part."""
    threads()
    cancelling()
    errors()
    processes()


if __name__ == "__main__":
    main()
