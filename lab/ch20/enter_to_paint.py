"""Time the path from Enter in the entry to the rows on the screen."""

import statistics
import time
import tkinter as tk

from tk_screenshot_gui import backend

from sift.gui.tk_app import HEIGHT, WIDTH, SearchWindow

QUERIES = ["rust 所有权", "kalman filter", "async await", "设备树 device"]
ROUNDS = 5


def one_round(window: SearchWindow, query: str) -> tuple[float, float]:
    """Return (ms until painted, ms the search itself took)."""
    root = window.root
    window.tree.delete(*window.tree.get_children())
    window.query.set(query)
    root.update()
    window.entry.focus_force()
    root.update()
    start = time.perf_counter()
    window.entry.event_generate("<Return>")
    while window.controller.pending or not window.tree.get_children():
        root.update()
        time.sleep(0.001)
    root.update_idletasks()
    root.update()  # the rows and the preview are drawn now
    painted = (time.perf_counter() - start) * 1000
    took = float(window.status_text.get().split("，")[1].split()[0])
    return painted, took


def main() -> None:
    """Measure Enter-to-paint for a few queries and print a table."""
    with backend() as searching_backend:
        root = tk.Tk()
        root.geometry(f"{WIDTH}x{HEIGHT}+0+0")
        window = SearchWindow(root, searching_backend, theme="light")
        root.update()
        one_round(window, "warm up")  # first use of the index pages
        print(f"{'query':<16} {'search':>9} {'Enter to painted':>18}")
        every: list[float] = []
        for query in QUERIES:
            painted_ms: list[float] = []
            took_ms: list[float] = []
            for _ in range(ROUNDS):
                painted, took = one_round(window, query)
                painted_ms.append(painted)
                took_ms.append(took)
            every += painted_ms
            print(
                f"{query:<16} {statistics.median(took_ms):7.1f} ms "
                f"{statistics.median(painted_ms):14.1f} ms"
            )
        print(
            f"median over {len(every)} runs: "
            f"{statistics.median(every):.1f} ms, "
            f"worst {max(every):.1f} ms"
        )
        root.destroy()


if __name__ == "__main__":
    main()
