"""Atomic writes: temp file + os.replace vs writing in place."""

import contextlib
import os
import tempfile
from pathlib import Path

from sift.storage.atomic import atomic_write


class Crash(Exception):
    """Stands for a power cut or a bug in the middle of a write."""


def naive_write(path: Path, text: str, *, crash: bool) -> None:
    """Overwrite in place; the file is empty until the write ends."""
    with path.open("w", encoding="utf-8") as file:
        file.write(text[: len(text) // 2])
        file.flush()
        if crash:
            raise Crash("died after half the data")
        file.write(text[len(text) // 2 :])


def chunks(text: str, *, crash: bool):
    """Yield the text in two halves, optionally dying in between."""
    yield text[: len(text) // 2].encode()
    if crash:
        raise Crash("died after half the data")
    yield text[len(text) // 2 :].encode()


def main() -> None:
    """Crash in the middle of a write, both ways."""
    with tempfile.TemporaryDirectory(prefix="sift-atomic-") as tmp:
        path = Path(tmp) / "manifest.json"
        path.write_text('{"version": 1}\n')
        print("start          :", path.read_text().strip())

        with contextlib.suppress(Crash):
            naive_write(path, '{"version": 2, "files": []}\n', crash=True)
        print("naive, crash   :", repr(path.read_text()))

        path.write_text('{"version": 1}\n')
        with contextlib.suppress(Crash):
            atomic_write(path, chunks('{"version": 2}\n', crash=True))
        print("atomic, crash  :", repr(path.read_text()))
        print("temp files left:", sorted(os.listdir(tmp)))

        inode = path.stat().st_ino
        atomic_write(path, chunks('{"version": 2}\n', crash=False))
        print("atomic, ok     :", repr(path.read_text()))
        print("inode changed  :", path.stat().st_ino != inode)
        print("mode           :", oct(path.stat().st_mode & 0o777))

        print("--- a reader that keeps the old file open")
        with path.open() as old_reader:
            atomic_write(path, [b'{"version": 3}\n'])
            print("old reader sees:", old_reader.read().strip())
            print("new open sees  :", path.read_text().strip())

        print("--- os.replace needs the same file system")
        print("temp dir is next to the target:", Path(tmp) == path.parent)


if __name__ == "__main__":
    main()
