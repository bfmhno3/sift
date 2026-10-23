"""The same index as pickle, json, marshal and as a Sift segment.

Size in bytes and load time. The rounds alternate between formats and
the table shows the minimum and the median of the rounds, because the
machine switches between a fast and a slow CPU state.
"""

import json
import marshal
import pickle
import statistics
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from sift.cli import CORPUS
from sift.index import Posting, PostingList
from sift.storage.segment import Segment, write_segment
from sift.storage.store import open_index, update_index

NAMES = ("mixed", "nfkc", "stopwords")
ROUNDS = 7

type Postings = dict[str, list[tuple[int, tuple[int, ...]]]]


def load_postings(directory: Path) -> tuple[Postings, list[int]]:
    """Return every posting list as plain tuples, and the doc lengths."""
    with open_index(directory) as index:
        postings: Postings = {
            term: [(p.doc_id, p.positions) for p in plist]
            for term, plist in index.segment.iter_postings()
        }
        return postings, list(index.segment.doc_lens)


def segment_open(path: Path) -> None:
    """Open the segment: header and dictionary, no posting decoded."""
    with Segment(path):
        pass


def segment_all(path: Path) -> int:
    """Open the segment and decode every posting list."""
    with Segment(path) as segment:
        return sum(len(plist) for _, plist in segment.iter_postings())


def measure(jobs: dict[str, Callable[[], object]]) -> dict[str, list[float]]:
    """Run every job once per round, in turn; return milliseconds."""
    times: dict[str, list[float]] = {name: [] for name in jobs}
    for _ in range(ROUNDS):
        for name, job in jobs.items():
            start = time.perf_counter_ns()
            job()
            times[name].append((time.perf_counter_ns() - start) / 1e6)
    return times


def main() -> None:
    """Build the index once, write it four ways, time the loads."""
    with tempfile.TemporaryDirectory(prefix="sift-ser-") as tmp:
        root = Path(tmp)
        update_index(CORPUS, root / "idx", NAMES)
        postings, lengths = load_postings(root / "idx")
        n_postings = sum(len(plist) for plist in postings.values())
        print(f"terms {len(postings)}, postings {n_postings}")

        blobs = {
            "pickle": pickle.dumps((postings, lengths)),
            "json": json.dumps((postings, lengths)).encode(),
            "marshal": marshal.dumps((postings, lengths)),
        }
        files = {"segment": root / "plain.sft", "segment+zlib": root / "z.sft"}
        pairs = [
            (
                term,
                PostingList(Posting(d, pos) for d, pos in postings[term]),
            )
            for term in sorted(postings)
        ]
        write_segment(files["segment"], pairs, lengths)
        write_segment(files["segment+zlib"], pairs, lengths, compress=True)

        sizes = {name: len(blob) for name, blob in blobs.items()}
        sizes.update({name: p.stat().st_size for name, p in files.items()})
        jobs: dict[str, Callable[[], object]] = {
            "pickle": lambda: pickle.loads(blobs["pickle"]),
            "json": lambda: json.loads(blobs["json"]),
            "marshal": lambda: marshal.loads(blobs["marshal"]),
            "segment (open)": lambda: segment_open(files["segment"]),
            "segment (decode all)": lambda: segment_all(files["segment"]),
            "segment+zlib (decode all)": lambda: segment_all(
                files["segment+zlib"]
            ),
        }
        times = measure(jobs)

        print(
            f"{'format':<28}{'bytes':>10}{'vs pickle':>11}"
            f"{'min ms':>9}{'median ms':>11}"
        )
        base = sizes["pickle"]
        for name, ms in times.items():
            size = sizes[name.split(" (")[0]]
            print(
                f"{name:<28}{size:>10}{size / base:>10.2f}x"
                f"{min(ms):>9.1f}{statistics.median(ms):>11.1f}"
            )
        print(f"(rounds: {ROUNDS}, alternating formats)")


if __name__ == "__main__":
    main()
