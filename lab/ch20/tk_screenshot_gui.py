"""Search in the Tk window and save a screenshot of the screen."""

import argparse
import subprocess
import tempfile
import time
import tkinter as tk
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast, get_args

from sift.cli import index_dir, searching
from sift.config import load_config
from sift.gui.controller import IndexBackend
from sift.gui.tk_app import HEIGHT, WIDTH, SearchWindow, Theme
from sift.storage.store import SEGMENT, update_index


@contextmanager
def backend() -> Iterator[IndexBackend]:
    """Yield a backend on the index of the config.

    If there is no index yet, one is built in a temp directory, so
    that the script runs alone.
    """
    config = load_config()
    directory = index_dir(config)
    with tempfile.TemporaryDirectory() as scratch:
        if not (directory / SEGMENT).is_file():
            directory = Path(scratch)
            update_index(config.corpus, directory, config.pipeline)
        with searching(directory, config) as searcher:
            yield IndexBackend(searcher, config.limit)


def show_results(window: SearchWindow, query: str) -> None:
    """Type query in the entry, press Enter, wait for the rows."""
    root = window.root
    window.query.set(query)
    root.update()
    window.entry.focus_force()
    root.update()
    window.entry.event_generate("<Return>")
    deadline = time.monotonic() + 30
    while window.controller.pending or not window.tree.get_children():
        root.update()
        if time.monotonic() > deadline:
            raise TimeoutError(f"no results for {query!r}")
        time.sleep(0.005)
    for _ in range(5):
        root.update()
        time.sleep(0.05)


def main() -> None:
    """Parse the options, open the window at +0+0, save the screen."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--theme", choices=get_args(Theme.__value__), default="light"
    )
    parser.add_argument("--query", default="rust 所有权")
    parser.add_argument(
        "--out", type=Path, default=Path("out/ch20/tk-smoke.png")
    )
    args = parser.parse_args()
    theme = cast(Theme, args.theme)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with backend() as searching_backend:
        root = tk.Tk()
        root.geometry(f"{WIDTH}x{HEIGHT}+0+0")
        window = SearchWindow(root, searching_backend, theme=theme)
        show_results(window, args.query)
        print("status:", window.status_text.get())
        print("rows:", len(window.tree.get_children()))
        subprocess.run(
            [
                "import",
                "-window",
                "root",
                "-crop",
                f"{WIDTH}x{HEIGHT}+0+0",
                str(args.out),
            ],
            check=True,
        )
        root.destroy()
    print(f"saved {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
