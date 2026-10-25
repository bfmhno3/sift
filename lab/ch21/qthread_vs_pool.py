"""QThread against QThreadPool: where the work runs, what it costs.

One ``QThread`` per job is a thread to create, start and wait for.
A ``QRunnable`` on the global ``QThreadPool`` reuses worker threads.
Both report back with a signal, which Qt delivers on the thread of the
receiver: the slot of a main-thread object runs on the main thread.
Times are a median of 5 runs, so they differ from machine to machine;
the ratio is what to look at.
"""

import os
import statistics
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
    Signal,
)

JOBS = 200


class Done(QObject):
    """Receives results; lives in the main thread."""

    ready = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self.threads: set[str] = set()
        self.ready.connect(self.on_ready)

    def on_ready(self, _value: int) -> None:
        self.count += 1
        self.threads.add(threading.current_thread().name)


class Job(QRunnable):
    def __init__(self, done: Done, value: int) -> None:
        super().__init__()
        self.done = done
        self.value = value

    def run(self) -> None:
        self.done.ready.emit(self.value)


class Thread(QThread):
    def __init__(self, done: Done, value: int) -> None:
        super().__init__()
        self.done = done
        self.value = value

    def run(self) -> None:
        self.done.ready.emit(self.value)


def with_threads(app: QCoreApplication, done: Done) -> float:
    """Start JOBS QThreads, wait for each, return seconds."""
    start = time.perf_counter()
    for value in range(JOBS):
        thread = Thread(done, value)
        thread.start()
        thread.wait()
    app.processEvents()
    return time.perf_counter() - start


def with_pool(app: QCoreApplication, done: Done) -> float:
    """Queue JOBS runnables on the global pool, return seconds."""
    pool = QThreadPool.globalInstance()
    start = time.perf_counter()
    for value in range(JOBS):
        pool.start(Job(done, value))
    pool.waitForDone()
    app.processEvents()
    return time.perf_counter() - start


def main() -> None:
    app = QCoreApplication(sys.argv)
    done = Done()
    print("main thread:", threading.current_thread().name)
    times: dict[str, list[float]] = {"QThread": [], "QThreadPool": []}
    for _ in range(5):
        times["QThread"].append(with_threads(app, done))
        times["QThreadPool"].append(with_pool(app, done))
    print("slots ran:", done.count, "of", 10 * JOBS)
    print("slots ran on:", sorted(done.threads))
    medians = {k: statistics.median(v) * 1000 for k, v in times.items()}
    for name, ms in medians.items():
        print(f"{name:12} {ms:8.2f} ms for {JOBS} jobs")
    ratio = medians["QThread"] / medians["QThreadPool"]
    print(f"ratio QThread / pool: {ratio:.1f}x")


if __name__ == "__main__":
    main()
