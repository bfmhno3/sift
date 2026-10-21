"""A generator as a coroutine: send(), throw() and close()."""

from collections.abc import Generator


def averager() -> Generator[float | None, float | None, str]:
    """Receive numbers with send() and yield the running mean."""
    total = 0.0
    count = 0
    mean: float | None = None
    try:
        while True:
            try:
                value = yield mean
            except ValueError as exc:
                print("  generator caught ValueError:", exc)
                total, count, mean = 0.0, 0, None
                continue
            if value is None:
                continue
            total += value
            count += 1
            mean = total / count
    except GeneratorExit:
        print("  generator got GeneratorExit, cleaning up")
        raise
    finally:
        print("  finally: saw", count, "values")


def main() -> None:
    """Drive the averager with send, throw and close."""
    gen = averager()
    print("prime with next:", next(gen))
    print("send 10:", gen.send(10))
    print("send 20:", gen.send(20))
    print("send 60:", gen.send(60))
    print("throw ValueError:")
    print("  returned:", gen.throw(ValueError("reset")))
    print("send 5:", gen.send(5))
    print("close:")
    print("  returned:", gen.close())
    try:
        gen.send(1)
    except StopIteration:
        print("send after close: StopIteration")

    fresh = averager()
    try:
        fresh.send(1)
    except TypeError as exc:
        print("send to unstarted generator:", exc)

    # An uncaught throw() propagates out of the generator.
    gen = averager()
    next(gen)
    try:
        gen.throw(KeyError("boom"))
    except KeyError as exc:
        print("throw KeyError escapes:", exc)


if __name__ == "__main__":
    main()
