"""Hand results from worker threads to Tk through a Queue."""

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

POLL_MS = 30


def main() -> None:
    """Start three workers; the UI thread drains the queue."""
    root = tk.Tk()
    root.geometry("320x120+0+0")
    label = ttk.Label(root, text="waiting")
    label.pack(padx=16, pady=16)
    results: queue.Queue[tuple[int, str, str]] = queue.Queue()

    # 1. A widget call from another thread, while the main loop is not
    #    running, is refused.
    def touch() -> None:
        try:
            label.configure(text="from a thread")
        except RuntimeError as error:
            results.put((-1, threading.current_thread().name, str(error)))

    probe = threading.Thread(target=touch, name="probe")
    probe.start()
    probe.join()
    _, name, message = results.get_nowait()
    print(f"widget call from {name} before mainloop: RuntimeError")
    print(f"  {message}")

    # 2. The pattern: workers put plain data, the UI thread reads it.
    def worker(number: int) -> None:
        time.sleep(0.05 * (4 - number))
        results.put((number, threading.current_thread().name, "done"))

    threads = [
        threading.Thread(target=worker, args=(n,), name=f"worker-{n}")
        for n in (1, 2, 3)
    ]
    for thread in threads:
        thread.start()

    arrived: list[str] = []
    ui_thread = threading.current_thread().name

    def poll() -> None:
        try:
            while True:
                number, name, state = results.get_nowait()
                label.configure(text=f"{name} {state}")
                arrived.append(f"{number}:{name}")
        except queue.Empty:
            pass
        if len(arrived) < 3:
            root.after(POLL_MS, poll)
        else:
            root.destroy()

    root.after(POLL_MS, poll)
    root.mainloop()
    for thread in threads:
        thread.join()
    print("polled by:", ui_thread)
    print("arrival order (slowest started first):", ", ".join(arrived))
    print("all results seen on the UI thread:", len(arrived) == 3)


if __name__ == "__main__":
    main()
