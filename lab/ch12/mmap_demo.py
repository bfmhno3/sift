"""mmap: a file as a bytes-like object, and what that buys.

Maps a real segment, slices it, searches it and reads random
records through mmap and through seek/read.
"""

import mmap
import os
import random
import statistics
import tempfile
import time
from pathlib import Path

from sift.cli import CORPUS
from sift.storage.segment import HEADER, MAGIC
from sift.storage.store import SEGMENT, update_index

NAMES = ("mixed", "nfkc", "stopwords")
READS = 20000
ROUNDS = 7


def basics(path: Path) -> None:
    """Map the segment read-only and use it like bytes."""
    with (
        path.open("rb") as file,
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mapped,
    ):
        print("len(mapped)    :", len(mapped), "bytes")
        print("magic          :", mapped[:4], mapped[:4] == MAGIC)
        print("header fields  :", HEADER.unpack_from(mapped, 0))
        print("find(b'SIFT')  :", mapped.find(b"SIFT"))
        print("slice copies   :", type(mapped[8:12]).__name__)
        view = memoryview(mapped)[8:12]
        print("memoryview     :", type(view).__name__, bytes(view).hex())
        view.release()
        try:
            mapped[0] = 0
        except TypeError as error:
            print("write to ACCESS_READ:", error)
        print("page size      :", mmap.PAGESIZE)


def copy_on_write(path: Path) -> None:
    """ACCESS_COPY lets you write to memory, never to the file."""
    before = path.read_bytes()[:4]
    with (
        path.open("rb") as file,
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_COPY) as mapped,
    ):
        mapped[:4] = b"XXXX"
        print("in memory      :", mapped[:4])
    print("on disk        :", before, "==", path.read_bytes()[:4])


def random_reads(path: Path) -> None:
    """Read many 8-byte records from random offsets two ways."""
    size = path.stat().st_size
    rng = random.Random(1234)
    offsets = [rng.randrange(0, size - 8) for _ in range(READS)]

    def with_mmap() -> int:
        total = 0
        with (
            path.open("rb") as file,
            mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mapped,
        ):
            for off in offsets:
                total += mapped[off : off + 8][0]
        return total

    def with_seek(buffering: int) -> int:
        total = 0
        with path.open("rb", buffering=buffering) as file:
            for off in offsets:
                file.seek(off)
                total += file.read(8)[0]
        return total

    def with_pread() -> int:
        total = 0
        with path.open("rb") as file:
            for off in offsets:
                total += os.pread(file.fileno(), 8, off)[0]
        return total

    jobs = {
        "mmap slice": with_mmap,
        "seek + read (buffered)": lambda: with_seek(-1),
        "seek + read (raw)": lambda: with_seek(0),
        "os.pread": with_pread,
    }
    assert len({job() for job in jobs.values()}) == 1
    times: dict[str, list[float]] = {name: [] for name in jobs}
    for _ in range(ROUNDS):
        for name, job in jobs.items():
            start = time.perf_counter_ns()
            job()
            times[name].append((time.perf_counter_ns() - start) / 1e6)
    print(f"{READS} random reads, {ROUNDS} alternating rounds (ms):")
    for name, ms in times.items():
        print(
            f"  {name:<24} min {min(ms):6.2f}  "
            f"median {statistics.median(ms):6.2f}"
        )


def main() -> None:
    """Index the corpus into a temp dir and map its segment."""
    with tempfile.TemporaryDirectory(prefix="sift-mmap-") as tmp:
        update_index(CORPUS, Path(tmp), NAMES)
        path = Path(tmp) / SEGMENT
        print("--- the mapping")
        basics(path)
        print("--- copy on write")
        copy_on_write(path)
        print("--- random access")
        random_reads(path)


if __name__ == "__main__":
    main()
