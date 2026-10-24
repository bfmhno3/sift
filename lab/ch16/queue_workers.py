"""queue.Queue: producers, workers, task_done, shutdown, limits."""

import queue
import threading

STOP = None


def worker(tasks: queue.Queue[int | None], results: queue.Queue[int]) -> None:
    """Square numbers until the sentinel arrives."""
    while True:
        item = tasks.get()
        try:
            if item is STOP:
                return
            results.put(item * item)
        finally:
            tasks.task_done()


def pipeline() -> None:
    """One producer (this thread), three workers, one sentinel each."""
    print("-- producer / consumer with sentinels")
    tasks: queue.Queue[int | None] = queue.Queue()
    results: queue.Queue[int] = queue.Queue()
    threads = [
        threading.Thread(target=worker, args=(tasks, results))
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for n in range(10):
        tasks.put(n)
    for _ in threads:
        tasks.put(STOP)
    tasks.join()
    squares = sorted(results.get() for _ in range(results.qsize()))
    print("  squares (sorted, arrival order is not defined):", squares)
    for thread in threads:
        thread.join()


def bounded() -> None:
    """A full queue blocks or raises: that is back pressure."""
    print("-- maxsize and the two ways to fail")
    small: queue.Queue[int] = queue.Queue(maxsize=2)
    small.put(1)
    small.put(2)
    try:
        small.put(3, block=False)
    except queue.Full:
        print("  put(block=False) on a full queue -> queue.Full")
    try:
        small.put(3, timeout=0.05)
    except queue.Full:
        print("  put(timeout=0.05) on a full queue -> queue.Full")
    small.get()
    small.get()
    try:
        small.get(block=False)
    except queue.Empty:
        print("  get(block=False) on an empty queue -> queue.Empty")


def other_kinds() -> None:
    """LIFO and priority queues share the interface."""
    print("-- LifoQueue and PriorityQueue")
    lifo: queue.LifoQueue[str] = queue.LifoQueue()
    for word in ("a", "b", "c"):
        lifo.put(word)
    print("  LifoQueue  :", [lifo.get() for _ in range(3)])
    prio: queue.PriorityQueue[tuple[int, str]] = queue.PriorityQueue()
    for item in ((3, "low"), (1, "urgent"), (2, "normal")):
        prio.put(item)
    print("  Priority   :", [prio.get()[1] for _ in range(3)])


def shutdown() -> None:
    """Queue.shutdown (3.13) ends the workers without sentinels."""
    print("-- Queue.shutdown() replaces the sentinels")
    tasks: queue.Queue[int] = queue.Queue()
    done: list[int] = []

    def drain() -> None:
        try:
            while True:
                done.append(tasks.get() + 100)
                tasks.task_done()
        except queue.ShutDown:
            done.append(-1)

    thread = threading.Thread(target=drain)
    thread.start()
    for n in range(3):
        tasks.put(n)
    tasks.join()
    tasks.shutdown()
    thread.join()
    print("  processed then told to stop:", done)
    try:
        tasks.put(9)
    except queue.ShutDown:
        print("  put after shutdown -> queue.ShutDown")


def main() -> None:
    """Run every demo."""
    pipeline()
    bounded()
    other_kinds()
    shutdown()


if __name__ == "__main__":
    main()
