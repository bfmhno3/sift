"""Lock, RLock, Condition, Event, Semaphore and Barrier in use."""

import threading
import time


def lock_demo() -> None:
    """A Lock makes a read-modify-write atomic; it is not re-entrant."""
    print("-- Lock")
    lock = threading.Lock()
    total = 0

    def add(n: int) -> None:
        nonlocal total
        for _ in range(n):
            with lock:
                total += 1

    threads = [threading.Thread(target=add, args=(20_000,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print("  4 threads x 20000 increments under a Lock ->", total)
    with lock:
        print("  locked() inside the with:", lock.locked())
        print("  acquire(blocking=False)  :", lock.acquire(blocking=False))
        print("  acquire(timeout=0.05)    :", lock.acquire(timeout=0.05))
    print("  locked() after the with  :", lock.locked())


def rlock_demo() -> None:
    """An RLock can be taken again by the thread that holds it."""
    print("-- RLock")
    rlock = threading.RLock()

    def outer() -> str:
        with rlock:
            return inner()

    def inner() -> str:
        with rlock:
            return "inner got the lock the outer already holds"

    print(" ", outer())
    plain = threading.Lock()
    with plain:
        print("  the same shape with a Lock times out:", end=" ")
        print(not plain.acquire(timeout=0.05))


def condition_demo() -> None:
    """A Condition lets a thread sleep until a predicate holds."""
    print("-- Condition")
    box: list[int] = []
    cond = threading.Condition()
    log: list[str] = []

    def consumer() -> None:
        with cond:
            cond.wait_for(lambda: len(box) >= 3)
            log.append(f"consumer woke with {box}")

    thread = threading.Thread(target=consumer)
    thread.start()
    for value in (1, 2, 3):
        time.sleep(0.02)
        with cond:
            box.append(value)
            log.append(f"producer put {value}")
            cond.notify()
    thread.join()
    for line in log:
        print("  ", line)


def event_demo() -> None:
    """An Event is a flag that threads can wait for."""
    print("-- Event")
    ready = threading.Event()
    seen: list[str] = []

    def waiter(name: str) -> None:
        ready.wait()
        seen.append(name)

    threads = [
        threading.Thread(target=waiter, args=(f"t{i}",)) for i in range(3)
    ]
    for thread in threads:
        thread.start()
    time.sleep(0.05)
    print("  waiters so far:", seen, "is_set:", ready.is_set())
    ready.set()
    for thread in threads:
        thread.join()
    print("  after set():", sorted(seen), "is_set:", ready.is_set())
    print("  wait(0.01) on an unset Event:", threading.Event().wait(0.01))


def semaphore_demo() -> None:
    """A Semaphore(2) lets at most two threads in at once."""
    print("-- Semaphore")
    gate = threading.Semaphore(2)
    guard = threading.Lock()
    inside = peak = 0

    def visit() -> None:
        nonlocal inside, peak
        with gate:
            with guard:
                inside += 1
                peak = max(peak, inside)
            time.sleep(0.03)
            with guard:
                inside -= 1

    threads = [threading.Thread(target=visit) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print("  6 threads, Semaphore(2): at most inside at once ->", peak)
    bounded = threading.BoundedSemaphore(1)
    bounded.acquire()
    bounded.release()
    try:
        bounded.release()
    except ValueError as error:
        print("  BoundedSemaphore released too often:", error)


def barrier_demo() -> None:
    """A Barrier makes every thread wait for the others."""
    print("-- Barrier")
    barrier = threading.Barrier(3)
    order: list[str] = []

    def party(i: int) -> None:
        time.sleep(0.02 * i)
        order.append(f"t{i} arrives")
        barrier.wait()
        order.append(f"t{i} leaves")

    threads = [threading.Thread(target=party, args=(i,)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    arrivals = [line for line in order if "arrives" in line]
    print("  all arrivals come before every departure:", order[:3] == arrivals)


def main() -> None:
    """Run every demo."""
    lock_demo()
    rlock_demo()
    condition_demo()
    event_demo()
    semaphore_demo()
    barrier_demo()


if __name__ == "__main__":
    main()
