"""Two locks taken in opposite order: acquire(timeout=1) detects it."""

import sys
import threading

lock_a = threading.Lock()
lock_b = threading.Lock()
both_hold_one = threading.Barrier(2)
verdicts: list[str] = []


def grab(name: str, first: threading.Lock, second: threading.Lock) -> None:
    """Hold first, wait for the other thread to hold its first, then
    ask for second with a timeout instead of forever."""
    with first:
        both_hold_one.wait()
        if second.acquire(timeout=1):
            second.release()
            verdicts.append(f"{name}: got both locks")
        else:
            verdicts.append(f"{name}: gave up after 1 s, deadlock")


def main() -> None:
    """Run the two threads and exit 1 if the deadlock was detected."""
    threads = [
        threading.Thread(target=grab, args=("t1", lock_a, lock_b)),
        threading.Thread(target=grab, args=("t2", lock_b, lock_a)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for line in sorted(verdicts):
        print(line)
    if any("deadlock" in line for line in verdicts):
        print("lock order t1: a, b; t2: b, a -> take locks in one order")
        sys.exit(1)


if __name__ == "__main__":
    main()
