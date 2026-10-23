"""Compress the postings block with zlib, bz2, lzma and zstd.

The block is the postings part of the real segment (all terms, about
1.9 MB). Ratio is compressed / original. Times are the minimum and the
median of alternating rounds.
"""

import bz2
import lzma
import statistics
import tempfile
import time
import zlib
from collections.abc import Callable
from compression import zstd
from pathlib import Path

from sift.cli import CORPUS
from sift.storage.segment import HEADER
from sift.storage.store import SEGMENT, update_index

NAMES = ("mixed", "nfkc", "stopwords")
ROUNDS = 5


def postings_block() -> bytes:
    """Build the index in a temp dir; return its postings bytes."""
    with tempfile.TemporaryDirectory(prefix="sift-comp-") as tmp:
        update_index(CORPUS, Path(tmp), NAMES)
        data = (Path(tmp) / SEGMENT).read_bytes()
    post_off = HEADER.unpack_from(data)[6]
    return data[post_off:]


def codecs() -> dict[str, tuple[Callable, Callable]]:
    """Return name -> (compress, decompress) for every setting."""
    return {
        "zlib 1": (lambda b: zlib.compress(b, 1), zlib.decompress),
        "zlib 6": (lambda b: zlib.compress(b, 6), zlib.decompress),
        "zlib 9": (lambda b: zlib.compress(b, 9), zlib.decompress),
        "bz2 9": (lambda b: bz2.compress(b, 9), bz2.decompress),
        "lzma 6": (lambda b: lzma.compress(b, preset=6), lzma.decompress),
        "zstd 1": (lambda b: zstd.compress(b, 1), zstd.decompress),
        "zstd 3": (lambda b: zstd.compress(b, 3), zstd.decompress),
        "zstd 19": (lambda b: zstd.compress(b, 19), zstd.decompress),
    }


def main() -> None:
    """Print ratio and speed of every codec."""
    data = postings_block()
    print(f"postings block: {len(data)} bytes")
    table = codecs()
    packed = {name: comp(data) for name, (comp, _) in table.items()}
    for name, (_, decomp) in table.items():
        assert decomp(packed[name]) == data, name
    comp_ms: dict[str, list[float]] = {name: [] for name in table}
    decomp_ms: dict[str, list[float]] = {name: [] for name in table}
    for _ in range(ROUNDS):
        for name, (comp, decomp) in table.items():
            start = time.perf_counter_ns()
            comp(data)
            comp_ms[name].append((time.perf_counter_ns() - start) / 1e6)
            start = time.perf_counter_ns()
            decomp(packed[name])
            decomp_ms[name].append((time.perf_counter_ns() - start) / 1e6)
    print(
        f"{'codec':<8}{'bytes':>9}{'ratio':>8}"
        f"{'comp min':>10}{'comp med':>10}"
        f"{'decomp min':>12}{'decomp med':>12}  (ms)"
    )
    for name in table:
        size = len(packed[name])
        print(
            f"{name:<8}{size:>9}{size / len(data):>8.3f}"
            f"{min(comp_ms[name]):>10.1f}"
            f"{statistics.median(comp_ms[name]):>10.1f}"
            f"{min(decomp_ms[name]):>12.1f}"
            f"{statistics.median(decomp_ms[name]):>12.1f}"
        )
    print(f"(rounds: {ROUNDS}, alternating codecs; zstd {zstd.zstd_version})")
    # 每个 term 单独压缩时（segment 的做法）比整块压缩差多少
    print("--- per-term blocks, as the segment stores them")
    with tempfile.TemporaryDirectory(prefix="sift-comp-") as tmp:
        plain = update_index(CORPUS, Path(tmp), NAMES, full=True)
        packed_report = update_index(
            CORPUS, Path(tmp), NAMES, full=True, compress=True
        )
    print(f"segment plain: {plain.size} bytes")
    print(f"segment zlib : {packed_report.size} bytes")


if __name__ == "__main__":
    main()
