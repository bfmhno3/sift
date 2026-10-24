"""An unsynchronized counter shared by 8 threads loses updates."""

import sys
import threading

THREADS = 8
PER_THREAD = 200_000


class Counter:
    """A number in an attribute, the thing the threads fight over."""

    def __init__(self) -> None:
        self.value = 0


def bump(value: int) -> int:
    """Add one; a Python call, so a thread switch can happen here."""
    return value + 1


def plain(counter: Counter) -> None:
    """The statement everybody writes: read, add, write back."""
    for _ in range(PER_THREAD):
        counter.value += 1


def with_call(counter: Counter) -> None:
    """Same read-modify-write, with a function call in the middle."""
    for _ in range(PER_THREAD):
        seen = counter.value
        counter.value = bump(seen)


def locked(counter: Counter, lock: threading.Lock) -> None:
    """Same as plain, with the update under a Lock."""
    for _ in range(PER_THREAD):
        with lock:
            counter.value += 1


def run(label: str, kind: str) -> int:
    """Run THREADS threads; return the number of lost updates."""
    counter = Counter()
    lock = threading.Lock()
    targets = {
        "plain": lambda: plain(counter),
        "call": lambda: with_call(counter),
        "lock": lambda: locked(counter, lock),
    }
    threads = [threading.Thread(target=targets[kind]) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    expected = THREADS * PER_THREAD
    lost = expected - counter.value
    print(
        f"  {label:<34} expected {expected}, got {counter.value}, lost {lost}"
    )
    return lost


def main() -> None:
    """Run the three variants and print the lost updates."""
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"python {sys.version.split()[0]}, GIL enabled: {gil}")
    print(f"switch interval: {sys.getswitchinterval()} s")
    print("lost-update counts vary from run to run; 0 is possible:")
    run("counter.value += 1", "plain")
    run("read, bump() call, write back", "call")
    lost = run("counter.value += 1 under a Lock", "lock")
    if lost:
        sys.exit("the Lock failed to protect the counter")


if __name__ == "__main__":
    main()
