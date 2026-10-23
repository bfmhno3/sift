"""Atomic file replacement."""

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path


def atomic_write(path: Path, chunks: Iterable[bytes]) -> None:
    """Replace path with the concatenated chunks, all or nothing.

    The bytes go to a temporary file in the same directory, are
    flushed to disk, and ``os.replace`` renames the file over path. A
    reader sees the old file or the new one, never half of it. The
    temporary file is removed if anything fails. The new file gets
    mode 0644 (``NamedTemporaryFile`` would leave it at 0600).
    """
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as tmp:
        try:
            for chunk in chunks:
                tmp.write(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())
            os.chmod(tmp.name, 0o644)
            os.replace(tmp.name, path)
        except BaseException:
            os.unlink(tmp.name)
            raise
