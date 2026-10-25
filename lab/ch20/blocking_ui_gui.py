"""Block the UI thread for a second, then do the same on a worker."""

import statistics
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

TICK_MS = 10
WORK_S = 1.0
ROUND_TO_MS = 100


class Ticker:
    """Schedule after(TICK_MS) over and over; record how late it ran."""

    def __init__(self, root: tk.Tk) -> None:
        """Keep root and start the first tick."""
        self.root = root
        self.late_ms: list[float] = []
        self.running = True
        self._due = time.perf_counter() + TICK_MS / 1000
        root.after(TICK_MS, self._tick)

    def _tick(self) -> None:
        """Record the delay and schedule the next tick."""
        now = time.perf_counter()
        self.late_ms.append((now - self._due) * 1000)
        if self.running:
            self._due = now + TICK_MS / 1000
            self.root.after(TICK_MS, self._tick)

    def worst(self) -> float:
        """Return the largest delay seen, in ms."""
        return max(self.late_ms)


def rounded(ms: float) -> int:
    """Round ms to the nearest ROUND_TO_MS, for stable output."""
    return round(ms / ROUND_TO_MS) * ROUND_TO_MS


def run_case(root: tk.Tk, button: ttk.Button, threaded: bool) -> Ticker:
    """Click the button, wait for the work, return the ticker."""
    done = tk.BooleanVar(root, value=False)

    def work() -> None:
        time.sleep(WORK_S)

    def on_click() -> None:
        if threaded:
            # The thread sleeps; the UI thread goes back to the loop.
            # It only sets a flag: a variable is not touched from the
            # thread, the `after` below polls a plain Python object.
            thread = threading.Thread(target=work)
            thread.start()

            def check() -> None:
                if thread.is_alive():
                    root.after(30, check)
                else:
                    done.set(True)

            root.after(30, check)
        else:
            work()  # BAD: the UI thread sleeps, nothing is redrawn
            done.set(True)

    button.configure(command=on_click)
    root.update()
    ticker = Ticker(root)
    root.after(50, button.invoke)
    root.wait_variable(done)
    root.after(100, lambda: None)
    root.update()
    ticker.running = False
    root.update()
    return ticker


def main() -> None:
    """Measure the worst tick delay with each kind of handler."""
    root = tk.Tk()
    root.geometry("200x80+0+0")
    button = ttk.Button(root, text="work")
    button.pack(padx=16, pady=16)
    root.update()
    print(f"tick every {TICK_MS} ms, handler works {WORK_S:g} s")
    results: dict[str, float] = {}
    for name, threaded in (
        ("blocking handler", False),
        ("worker thread", True),
    ):
        ticker = run_case(root, button, threaded)
        results[name] = ticker.worst()
        typical = statistics.median(ticker.late_ms)
        print(
            f"{name:<17} worst tick delay: about {rounded(ticker.worst())} ms"
        )
        # exact values differ every run: stderr, not the checked text
        print(
            f"  exact: worst {ticker.worst():.1f} ms, "
            f"median {typical:.2f} ms, ticks {len(ticker.late_ms)}",
            file=sys.stderr,
        )
    stall = results["blocking handler"]
    worker = results["worker thread"]
    print("UI stalled for the whole second:", stall > 0.9 * WORK_S * 1000)
    print("UI kept running with a worker:", worker < 0.1 * WORK_S * 1000)
    root.destroy()


if __name__ == "__main__":
    main()
