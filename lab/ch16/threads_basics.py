"""Start, join and name threads; daemon threads and thread errors."""

import subprocess
import sys
import threading
import time

CHILD_DAEMON = (
    "import threading, time;"
    "threading.Thread(target=time.sleep, args=(60,), daemon=%s).start();"
    "print('main is done')"
)


def work(label: str, seconds: float, out: list[str]) -> None:
    """Sleep, then record who ran this in which thread."""
    time.sleep(seconds)
    out.append(f"{label} ran in {threading.current_thread().name}")


def boom() -> None:
    """Raise inside a thread."""
    raise RuntimeError("worker failed")


def run_child(daemon: bool) -> str:
    """Run a child interpreter; say if it exits within one second."""
    argv = [sys.executable, "-c", CHILD_DAEMON % daemon]
    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, timeout=1.0
        )
    except subprocess.TimeoutExpired:
        return "still running after 1 s (a non-daemon thread blocks exit)"
    return f"exit {done.returncode}, stdout {done.stdout.strip()!r}"


def main() -> None:
    """Show the life cycle of a Thread."""
    print("-- start and join")
    out: list[str] = []
    threads = [
        threading.Thread(
            target=work, args=(f"job{i}", 0.05 * (3 - i), out), name=f"w{i}"
        )
        for i in range(3)
    ]
    print("  before start:", [t.is_alive() for t in threads])
    for thread in threads:
        thread.start()
    print("  after start :", [t.is_alive() for t in threads])
    for thread in threads:
        thread.join()
    print("  after join  :", [t.is_alive() for t in threads])
    print("  finished in the order of the sleeps, not of the starts:")
    for line in out:
        print("   ", line)
    print("-- the main thread is a thread too")
    main_thread = threading.main_thread()
    print("  current is main:", threading.current_thread() is main_thread)
    print("  main name      :", main_thread.name)
    print("  active threads :", threading.active_count())
    print("-- join(timeout) returns, it does not say if the thread ended")
    slow = threading.Thread(target=time.sleep, args=(0.3,))
    slow.start()
    slow.join(timeout=0.01)
    print("  still alive after join(0.01):", slow.is_alive())
    slow.join()
    print("  alive after join()          :", slow.is_alive())
    print("-- an exception ends the thread, not the program")
    seen: list[str] = []
    old_hook = threading.excepthook
    threading.excepthook = lambda args: seen.append(
        f"{args.exc_type.__name__}: {args.exc_value} in {args.thread.name}"
        if args.thread
        else "?"
    )
    failing = threading.Thread(target=boom, name="failing")
    failing.start()
    failing.join()
    threading.excepthook = old_hook
    print("  join returned; excepthook saw:", seen)
    print("-- daemon threads do not keep the interpreter alive")
    print("  daemon=False:", run_child(False))
    print("  daemon=True :", run_child(True))
    print("-- the daemon flag is fixed once the thread has started")
    thread = threading.Thread(target=time.sleep, args=(0.01,))
    thread.start()
    try:
        thread.daemon = True
    except RuntimeError as error:
        print("  RuntimeError:", error)
    thread.join()


if __name__ == "__main__":
    main()
