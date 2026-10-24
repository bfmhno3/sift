"""concurrent.interpreters (PEP 734): isolated interpreters."""

import threading
from concurrent import interpreters
from concurrent.futures import InterpreterPoolExecutor


def double(n: int) -> int:
    """Called inside a subinterpreter."""
    return n * 2


def main() -> None:
    """Create interpreters, run code in them, pass data."""
    print("-- an interpreter is a separate world")
    main_interp = interpreters.get_main()
    print(
        "  main:",
        main_interp.id,
        "list_all ids:",
        [i.id for i in interpreters.list_all()],
    )
    interp = interpreters.create()
    interp.exec("greeting = 'hello from a subinterpreter'")
    interp.exec("print(greeting)")
    try:
        interp.exec("print(missing)")
    except interpreters.ExecutionFailed as error:
        print("  exec failed:", str(error).splitlines()[0])
    print("  here the name is unknown:", "greeting" not in globals())
    print("-- call(): run a function there, get its result back")
    print("  interp.call(double, 21):", interp.call(double, 21))
    print("-- prepare_main(): pass shareable data in")
    interp.prepare_main(count=3, label="spam", flag=True, blob=b"xyz")
    interp.exec("print('  main namespace there:', count, label, flag, blob)")
    try:
        interp.prepare_main(items=[1, 2])
    except interpreters.NotShareableError as error:
        print("  a list is not shareable:", error)
    print("-- a Queue carries values between interpreters")
    queue = interpreters.create_queue()
    interp.prepare_main(queue=queue)
    interp.exec("queue.put('one'); queue.put(2); queue.put(None)")
    print("  got:", [queue.get(), queue.get(), queue.get()])
    interp.close()
    print("  closed; list_all ids:", [i.id for i in interpreters.list_all()])
    print("-- call_in_thread(): the interpreter runs on its own thread")
    other = interpreters.create()
    other.prepare_main(n=5)
    thread = other.call_in_thread(double, 8)
    thread.join()
    print("  thread was a", type(thread).__name__)
    other.close()
    print("-- InterpreterPoolExecutor: the futures API over interpreters")
    with InterpreterPoolExecutor(2) as pool:
        print("  map(double):", list(pool.map(double, range(5))))
        print("  a lambda without closure:", pool.submit(lambda: 1).result())
        print(
            "  a list argument (pickled):", pool.submit(len, [1, 2]).result()
        )
        offset = 3
        try:
            pool.submit(lambda: offset).result()
        except interpreters.NotShareableError:
            print("  a lambda with a closure: NotShareableError")
    print("threads alive at the end:", threading.active_count())


if __name__ == "__main__":
    main()
