"""Search in the Qt window and save a screenshot of the window.

The window is drawn offscreen at a scale factor of 2, so the PNG is
2400 x 1520 pixels: the same size a HiDPI laptop shows. The script
also prints the numbers of the chapter: the time from process start
to the first painted frame (``QElapsedTimer``) and the time a search
takes on the pool thread against the frame interval of the screen.
"""

import os

# before Qt is imported: the scale factor is read when Qt starts
os.environ["QT_SCALE_FACTOR"] = "2"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import argparse  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import cast, get_args  # noqa: E402

from PySide6.QtCore import QElapsedTimer, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sift.cli import index_dir, searching  # noqa: E402
from sift.config import load_config  # noqa: E402
from sift.gui.controller import IndexBackend  # noqa: E402
from sift.gui.qt.theme import Scheme  # noqa: E402
from sift.gui.qt.window import MainWindow  # noqa: E402
from sift.storage.store import DB, SEGMENT, update_index  # noqa: E402


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
            yield IndexBackend(searcher, config.limit, log_path=directory / DB)


def wait_until(window: MainWindow, seconds: float = 30.0) -> None:
    """Run the event loop until the newest search has an answer."""
    deadline = time.monotonic() + seconds
    while window.searching:
        QTest.qWait(5)
        if time.monotonic() > deadline:
            raise TimeoutError("the search did not finish")


def report_responsiveness(window: MainWindow) -> None:
    """Search 7 more times while a 4 ms timer watches the UI thread.

    If the search ran on the UI thread, the timer would not fire for
    as long as the search takes. On a pool thread the longest gap
    between two ticks stays near the interval.
    """
    gaps: list[float] = []
    last = time.perf_counter()

    def tick() -> None:
        nonlocal last
        now = time.perf_counter()
        gaps.append((now - last) * 1000)
        last = now

    timer = QTimer()
    timer.setInterval(4)
    timer.timeout.connect(tick)
    timer.start()
    warm: list[float] = []
    apply: list[float] = []
    for _ in range(7):
        window.search_now()
        wait_until(window)
        warm.append(window.latency_ms)
        apply.append(window.apply_ms)
    timer.stop()
    print(
        f"warm request to rows, median of 7: {statistics.median(warm):.1f} ms"
    )
    print(
        f"UI thread work per answer (cards, preview): "
        f"{statistics.median(apply):.1f} ms median"
    )
    print(
        f"UI thread: {len(gaps)} ticks of 4 ms, longest gap {max(gaps):.1f} ms"
    )


def main() -> None:
    """Parse the options, open the window, search, save the image."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--theme", choices=get_args(Scheme.__value__), default="light"
    )
    parser.add_argument("--query", default="rust 所有权")
    parser.add_argument("--select", type=int, default=0)
    parser.add_argument(
        "--out", type=Path, default=Path("out/ch21/qt-smoke.png")
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    startup = QElapsedTimer()
    startup.start()
    app = QApplication(sys.argv)
    with backend() as searching_backend:
        window = MainWindow(
            searching_backend,
            scheme=cast(Scheme, args.theme),
            startup=startup,
        )
        window.show()
        while window.first_paint_ms is None:
            QTest.qWait(5)
        if args.query:
            window.search_edit.setText(args.query)
            window.search_now()
            wait_until(window)
            QTest.qWait(100)
            if window.model.rowCount() and args.select > 0:
                row = min(args.select, window.model.rowCount() - 1)
                window.list_view.setCurrentIndex(window.model.index(row))
        QTest.qWait(300)  # let the layout and the highlights settle

        refresh = app.primaryScreen().refreshRate()
        print("platform:", app.platformName())
        print("query:", repr(args.query), "rows:", window.model.rowCount())
        print("status:", window.status_label.text())
        print(f"first paint: {window.first_paint_ms} ms after start")
        if args.query:
            print(
                f"request to rows on screen: {window.latency_ms:.1f} ms "
                "(pool thread, signal back, cards, first preview)"
            )
            print(
                f"frame interval at {refresh:.0f} Hz: {1000 / refresh:.1f} ms"
            )
        image = window.grab()
        if not image.save(str(args.out)):
            raise SystemExit(f"cannot write {args.out}")
        print(
            f"saved {args.out} {image.width()}x{image.height()} "
            f"({args.out.stat().st_size} bytes)"
        )
        if args.query and window.model.rowCount():
            report_responsiveness(window)
        window.close()


if __name__ == "__main__":
    main()
