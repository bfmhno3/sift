"""multiprocessing: Pool.map, start methods and the cost of pickling."""

import multiprocessing as mp
import os
import pickle
import time

STATE = {"value": "set at import time"}


def square(n: int) -> int:
    """Run in a worker process."""
    return n * n


def look(_: int) -> tuple[bool, str]:
    """Report if this is another process and what STATE says there."""
    return os.getpid() != PARENT_PID, STATE["value"]


def length(data: list[int]) -> int:
    """Take a big argument; the cost is in sending it."""
    return len(data)


PARENT_PID = os.getpid()


def main() -> None:
    """Show the start methods, Pool.map and what pickling costs."""
    print("-- start method")
    print("  multiprocessing.get_start_method():", mp.get_start_method())
    print("  get_all_start_methods():", mp.get_all_start_methods())
    print("-- Pool.map with the default context")
    with mp.Pool(4) as pool:
        print("  squares:", pool.map(square, range(10)))
        print("  imap, chunksize 3:", list(pool.imap(square, range(6), 3)))
    print("-- what each start method gives a child")
    STATE["value"] = "changed in main() after the import"
    for method in ("fork", "spawn", "forkserver"):
        with mp.get_context(method).Pool(1) as pool:
            other, seen = pool.map(look, [0])[0]
            print(f"  {method:<10} other process: {other}, STATE: {seen!r}")
    print("-- pickling cost: the argument is copied through a pipe")
    data = list(range(2_000_000))
    start = time.perf_counter()
    blob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    dumped = time.perf_counter() - start
    start = time.perf_counter()
    pickle.loads(blob)
    loaded = time.perf_counter() - start
    with mp.Pool(1) as pool:
        pool.map(square, [1])  # start the worker first
        start = time.perf_counter()
        n = pool.apply(length, (data,))
        round_trip = time.perf_counter() - start
        start = time.perf_counter()
        pool.apply(square, (n,))
        small = time.perf_counter() - start
    print(f"  list of {n} ints pickles to {len(blob)} bytes")
    print("timing lines (vary between runs):")
    print(f"  pickle.dumps {dumped * 1000:8.2f} ms")
    print(f"  pickle.loads {loaded * 1000:8.2f} ms")
    print(f"  apply(length, data) {round_trip * 1000:8.2f} ms")
    print(f"  apply(square, 1)    {small * 1000:8.2f} ms")


if __name__ == "__main__":
    main()
