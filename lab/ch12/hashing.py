"""hashlib: sha256, file_digest and blake2b over the corpus."""

import hashlib
import hmac
import statistics
import time
from pathlib import Path

from sift.cli import CORPUS
from sift.storage.manifest import sha256_file

ROUNDS = 7


def chunked_sha256(path: Path) -> str:
    """Hash a file the long way: read 64 KiB at a time."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def file_digest(path: Path, name: str) -> str:
    """Hash a file with hashlib.file_digest (3.11+)."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, name).hexdigest()


def main() -> None:
    """Hash a few inputs, then time the corpus."""
    print("sha256(b'')    :", hashlib.sha256(b"").hexdigest())
    print("sha256(b'abc') :", hashlib.sha256(b"abc").hexdigest()[:32], "...")
    print("blake2b(b'abc'):", hashlib.blake2b(b"abc").hexdigest()[:32], "...")
    small = hashlib.blake2b(b"abc", digest_size=8)
    print("blake2b size 8 :", small.hexdigest(), small.digest_size, "bytes")
    text = "索引"
    print("str must be bytes:", hashlib.sha256(text.encode()).hexdigest()[:16])
    try:
        hashlib.sha256(text)  # type: ignore[arg-type]
    except TypeError as error:
        print("TypeError:", error)
    sha = hashlib.sha256()
    print("digest_size/block_size:", sha.digest_size, sha.block_size)
    print("sha256 in guaranteed:", "sha256" in hashlib.algorithms_guaranteed)

    first = sorted(CORPUS.glob("*.md"))[0]
    a = chunked_sha256(first)
    b = file_digest(first, "sha256")
    c = sha256_file(first)
    print("same digest three ways:", a == b == c)
    print("compare_digest:", hmac.compare_digest(a, b))

    files = sorted(CORPUS.glob("*.md"))
    total = sum(f.stat().st_size for f in files)
    print(f"--- {len(files)} files, {total / 1e6:.2f} MB")
    jobs = {
        "sha256 chunked": lambda: [chunked_sha256(f) for f in files],
        "sha256 file_digest": lambda: [
            file_digest(f, "sha256") for f in files
        ],
        "blake2b file_digest": lambda: [
            file_digest(f, "blake2b") for f in files
        ],
        "md5 file_digest": lambda: [file_digest(f, "md5") for f in files],
    }
    times: dict[str, list[float]] = {name: [] for name in jobs}
    for _ in range(ROUNDS):
        for name, job in jobs.items():
            start = time.perf_counter_ns()
            job()
            times[name].append((time.perf_counter_ns() - start) / 1e6)
    for name, ms in times.items():
        print(
            f"{name:<20} min {min(ms):6.2f} ms  "
            f"median {statistics.median(ms):6.2f} ms"
        )


if __name__ == "__main__":
    main()
