"""Touch a widget from a worker thread: Qt warns, or crashes.

Expected failure: the script exits 1 when Qt's cross-thread warning
arrives (``QObject::setParent: Cannot set parent, new parent is in a
different thread``). If Qt aborts instead, the process dies with a
signal and the exit status is non-zero too, which also counts.

The rule: widgets live in the GUI thread and only that thread may
touch them. A worker emits a signal and a slot in the GUI thread does
the touching (see ``qthread_vs_pool.py`` and ``sift.gui.qt.worker``).
"""

import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

warnings: list[str] = []


def handler(kind: QtMsgType, _context: object, message: str) -> None:
    """Keep every Qt message; the cross-thread ones are the point."""
    warnings.append(message)
    print(f"qt {kind.name}: {message}", file=sys.stderr)


def worker(window: QWidget, label: QLabel) -> None:
    """Do what a worker must never do: use a widget."""
    label.setText("written from a worker thread")  # silent, and wrong
    QLabel("child made in the worker", window)  # Qt warns here


def main() -> None:
    qInstallMessageHandler(handler)
    app = QApplication(sys.argv)
    window = QWidget()
    label = QLabel("main thread", window)
    window.show()
    thread = threading.Thread(target=worker, args=(window, label))
    thread.start()
    thread.join()
    app.processEvents()
    crossing = [m for m in warnings if "different thread" in m]
    print("cross-thread warnings:", len(crossing))
    if crossing:
        sys.exit(1)


if __name__ == "__main__":
    main()
