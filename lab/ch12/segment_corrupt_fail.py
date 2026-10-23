"""Open a segment whose magic number was damaged."""

# error: IndexCorruptError: segment.sft: bad magic b'XIFT', expected b'SIFT'

import contextlib
import tempfile
from pathlib import Path

from sift.storage.segment import Segment
from sift.storage.store import SEGMENT, update_index

MINI = Path("tests/fixtures/mini")


def main() -> None:
    """Index the mini fixture, damage the first byte, open the file."""
    source = MINI.resolve()
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        update_index(source, Path("."), ("mixed", "nfkc", "stopwords"))
        path = Path(SEGMENT)
        data = bytearray(path.read_bytes())
        data[0] = ord("X")  # the magic SIFT becomes XIFT
        path.write_bytes(data)
        with Segment(path):
            pass


if __name__ == "__main__":
    main()
