"""pathlib, plus the os, shutil and tempfile calls it sits next to."""

import contextlib
import os
import shutil
import tempfile
from pathlib import Path


def build_tree(root: Path) -> None:
    """Create a small tree of posts under root."""
    (root / "posts" / "rust").mkdir(parents=True)
    (root / "posts" / "cpp").mkdir()
    (root / "posts" / "rust" / "ownership.md").write_text("# own\n")
    (root / "posts" / "rust" / "lifetimes.md").write_text("# life\n")
    (root / "posts" / "cpp" / "raii.md").write_text("# raii\n")
    (root / "posts" / "notes.txt").write_text("not a post\n")


def tour_paths(root: Path) -> None:
    """Join, split and rewrite paths without touching the disk."""
    path = root / "posts" / "rust" / "ownership.md"
    print("relative_to :", path.relative_to(root))
    print("name        :", path.name)
    print("stem        :", path.stem)
    print("suffix      :", path.suffix)
    print("parent.name :", path.parent.name)
    print("parts[-3:]  :", path.parts[-3:])
    print("with_suffix :", path.with_suffix(".html").name)
    print("with_name   :", path.with_name("borrow.md").name)
    archive = Path("backup.tar.gz")
    print("suffixes    :", archive.suffixes, "stem:", archive.stem)
    print("joinpath    :", Path("a", "b") / "c" == Path("a/b/c"))
    print("absolute?   :", path.is_absolute(), Path("x").is_absolute())


def tour_disk(root: Path) -> None:
    """glob, rglob, read_text, stat and friends."""
    posts = root / "posts"
    print("glob *.txt   :", [p.name for p in sorted(posts.glob("*.txt"))])
    print("glob */*.md  :", [p.name for p in sorted(posts.glob("*/*.md"))])
    found = sorted(posts.rglob("*.md"))
    print("rglob *.md   :", [p.relative_to(posts).as_posix() for p in found])
    note = posts / "notes.txt"
    print("read_text    :", repr(note.read_text()))
    info = note.stat()
    print("stat.st_size :", info.st_size)
    print("mtime_ns type:", type(info.st_mtime_ns).__name__)
    print("exists/is_dir:", note.exists(), note.is_dir(), posts.is_dir())
    print("iterdir      :", sorted(p.name for p in posts.iterdir()))
    note.rename(posts / "notes.md")
    print("after rename :", sorted(p.name for p in posts.glob("notes.*")))
    (posts / "notes.md").unlink()


def tour_os_shutil(root: Path) -> None:
    """The older os and shutil spellings of the same operations."""
    posts = root / "posts"
    print("os.listdir   :", sorted(os.listdir(posts)))
    with os.scandir(posts) as entries:
        dirs = sorted(e.name for e in entries if e.is_dir())
    print("os.scandir   :", dirs)
    for here, folders, files in os.walk(posts):
        folders.sort()
        shown = Path(here).relative_to(root).as_posix()
        print("os.walk      :", shown, sorted(files))
    copy = root / "copy"
    shutil.copytree(posts, copy)
    print("copytree     :", len(list(copy.rglob("*.md"))), "files")
    shutil.copy2(copy / "cpp" / "raii.md", root / "raii-copy.md")
    shutil.move(root / "raii-copy.md", copy / "moved.md")
    print("copy2 + move :", (copy / "moved.md").read_text().strip())
    shutil.rmtree(copy)
    print("rmtree       :", copy.exists())
    print("os.cpu_count :", isinstance(os.cpu_count(), int))
    print("os.sep       :", repr(os.sep), "os.linesep:", repr(os.linesep))


def tour_tempfile() -> None:
    """The four tempfile entry points and what each one cleans up."""
    with tempfile.TemporaryDirectory(prefix="sift-demo-") as tmp:
        print("TemporaryDirectory:", Path(tmp).name.startswith("sift-demo-"))
    with tempfile.NamedTemporaryFile("w+", suffix=".txt") as named:
        named.write("hello")
        named.flush()
        print("NamedTemporaryFile:", Path(named.name).read_text())
    gone = named.name
    print("deleted on exit   :", not os.path.exists(gone))
    with tempfile.TemporaryFile() as anonymous:
        anonymous.write(b"no name in the file system")
        anonymous.seek(0)
        print("TemporaryFile     :", anonymous.read(9))
    made = tempfile.mkdtemp()
    print("mkdtemp stays     :", Path(made).is_dir())
    shutil.rmtree(made)


def main() -> None:
    """Run the tour in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        root = Path.cwd()
        build_tree(root)
        print("--- paths (no disk access)")
        tour_paths(root)
        print("--- paths on disk")
        tour_disk(root)
        print("--- os and shutil")
        tour_os_shutil(root)
    print("--- tempfile")
    tour_tempfile()
    corpus = Path("corpus/posts")
    print("--- the real corpus")
    print("posts:", len(list(corpus.glob("*.md"))))
    print("first:", sorted(corpus.glob("*.md"))[0].name)


if __name__ == "__main__":
    main()
