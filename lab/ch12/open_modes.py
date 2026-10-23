"""open(): text vs binary, newline translation, encodings, buffering."""

import contextlib
import io
import tempfile
from pathlib import Path


def io_stack(path: Path) -> None:
    """Show the layers behind open() in text, buffered and raw mode."""
    with path.open("r", encoding="utf-8") as text:
        print("text    :", type(text).__name__)
        print("  .buffer:", type(text.buffer).__name__)
        print("  .buffer.raw:", type(text.buffer.raw).__name__)
    with path.open("rb") as binary:
        print("binary  :", type(binary).__name__)
        print("  .raw  :", type(binary.raw).__name__)
    with path.open("rb", buffering=0) as raw:
        print("raw     :", type(raw).__name__)
    print("io.DEFAULT_BUFFER_SIZE:", io.DEFAULT_BUFFER_SIZE)


def text_vs_binary(path: Path) -> None:
    """The same file as str and as bytes."""
    path.write_text("索引 index\n", encoding="utf-8")
    print("read_text :", repr(path.read_text(encoding="utf-8")))
    print("read_bytes:", path.read_bytes())
    print(
        "len str:", len("索引 index\n"), "len bytes:", len(path.read_bytes())
    )


def newlines(path: Path) -> None:
    """Newline translation: what is on disk vs what Python gives you."""
    with path.open("w", encoding="utf-8", newline="\r\n") as file:
        file.write("one\ntwo\n")
    print("on disk        :", path.read_bytes())
    with path.open("r", encoding="utf-8") as file:
        print("default read   :", repr(file.read()))
    with path.open("r", encoding="utf-8", newline="") as file:
        print("newline='' read:", repr(file.read()))
    with path.open("r", encoding="utf-8", newline="\r\n") as file:
        print("newline='\\r\\n' :", repr(file.read()))


def encodings(path: Path) -> None:
    """Writing with one encoding and reading with another."""
    path.write_text("索引", encoding="utf-16")
    print("utf-16 bytes:", path.read_bytes())
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        print("read as utf-8:", type(error).__name__, error.reason)
    print("errors=replace:", repr(path.read_text("utf-8", errors="replace")))
    print("utf-8 BOM:", repr(b"\xef\xbb\xbfx".decode("utf-8-sig")))


def buffering(path: Path) -> None:
    """A buffered write is invisible to other readers until flush."""
    with path.open("wb") as file:
        file.write(b"hello")
        print("after write, size on disk:", path.stat().st_size)
        file.flush()
        print("after flush, size on disk:", path.stat().st_size)
    with path.open("wb", buffering=0) as raw:
        raw.write(b"hello")
        print("unbuffered, size on disk :", path.stat().st_size)
    with path.open("w", encoding="utf-8", buffering=1) as lines:
        lines.write("no newline yet")
        print("line-buffered, no \\n    :", path.stat().st_size)
        lines.write("\n")
        print("line-buffered, after \\n :", path.stat().st_size)


def seek_tell(path: Path) -> None:
    """seek/tell on text files: tell() is a cookie, not a byte count."""
    path.write_text("索引a\nb\n", encoding="utf-8")
    with path.open("r", encoding="utf-8") as text:
        print("readline  :", repr(text.readline()), "tell:", text.tell())
        try:
            text.seek(1)  # the middle of 索, which takes 3 bytes
            text.read()
        except UnicodeDecodeError as error:
            print("seek(1) + read:", type(error).__name__, error.reason)
    with path.open("r", encoding="utf-8") as text:
        for _ in text:
            break
        try:
            text.tell()
        except OSError as error:
            print("tell() after next():", error)
    with path.open("rb") as binary:
        binary.seek(3)
        print("binary seek(3) + read(1):", binary.read(1))


def modes(path: Path) -> None:
    """w truncates, a appends, x refuses to overwrite, r+ edits."""
    path.write_text("abc")
    with path.open("a") as file:
        file.write("def")
    print("after a :", path.read_text())
    with path.open("r+") as file:
        file.seek(1)
        file.write("XY")
    print("after r+:", path.read_text())
    try:
        path.open("x")
    except FileExistsError as error:
        print("x on existing file:", type(error).__name__)
    path.write_text("")
    print("after w :", repr(path.read_text()))


def main() -> None:
    """Run every demo in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        path = Path("demo.txt")
        path.write_text("x\n", encoding="utf-8")
        for step in (
            io_stack,
            text_vs_binary,
            newlines,
            encodings,
            buffering,
            seek_tell,
            modes,
        ):
            print(f"--- {step.__name__}")
            step(path)


if __name__ == "__main__":
    main()
