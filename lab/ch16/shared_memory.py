"""multiprocessing.shared_memory: one buffer, two processes, no copy."""

import multiprocessing as mp
import time
from multiprocessing import shared_memory

COUNT = 1_000_000


def fill(name: str, start: int, stop: int) -> None:
    """Attach to the block by name and write squares into a slice."""
    shm = shared_memory.SharedMemory(name=name, track=False)
    try:
        numbers = shm.buf.cast("Q")
        for i in range(start, stop):
            numbers[i] = i * i
        numbers.release()
    finally:
        shm.close()


def main() -> None:
    """Fill a shared block from two processes and read it here."""
    shm = shared_memory.SharedMemory(create=True, size=COUNT * 8)
    try:
        print("created a block of", COUNT * 8, "bytes (name not printed)")
        print("size >= requested:", shm.size >= COUNT * 8)
        half = COUNT // 2
        procs = [
            mp.Process(target=fill, args=(shm.name, 0, half)),
            mp.Process(target=fill, args=(shm.name, half, COUNT)),
        ]
        start = time.perf_counter()
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join()
        took = time.perf_counter() - start
        print("exit codes:", [proc.exitcode for proc in procs])
        view = shm.buf.cast("Q")
        print(
            "view[3], view[999], view[999999]:", view[3], view[999], view[-1]
        )
        print("sum of the first ten:", sum(view[:10]))
        view.release()
        print("timing line (varies):", f"{took * 1000:.1f} ms")
        print("-- ShareableList: a small fixed-size shared list")
        shared = shared_memory.ShareableList([1, 2.5, "three"])
        other = shared_memory.ShareableList(name=shared.shm.name)
        other[0] = 100
        print("  written through the other handle:", list(shared))
        other.shm.close()
        shared.shm.close()
        shared.shm.unlink()
    finally:
        shm.close()
        shm.unlink()
    print("block unlinked")


if __name__ == "__main__":
    main()
