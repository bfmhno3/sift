"""A generator is a suspended frame: gi_frame and its states."""

import inspect


def counter(limit: int):
    """Yield 0 .. limit - 1."""
    i = 0
    while i < limit:
        yield i
        i += 1


def main() -> None:
    """Print the frame state at each stage of a generator."""
    gen = counter(2)
    print("type:", type(gen).__name__)
    print("created:", inspect.getgeneratorstate(gen))
    print("  gi_frame is None:", gen.gi_frame is None)
    print("  gi_running:", gen.gi_running)
    print("  gi_suspended:", gen.gi_suspended)
    print("  locals:", gen.gi_frame.f_locals)
    print("  f_lineno:", gen.gi_frame.f_lineno)

    print("next:", next(gen))
    print("suspended:", inspect.getgeneratorstate(gen))
    print("  gi_suspended:", gen.gi_suspended)
    print("  locals:", gen.gi_frame.f_locals)
    print("  f_lineno:", gen.gi_frame.f_lineno)
    print("  gi_code:", gen.gi_code.co_name, gen.gi_code.co_varnames)

    print("next:", next(gen))
    print("next:", next(gen, "exhausted"))
    print("finished:", inspect.getgeneratorstate(gen))
    print("  gi_frame is None:", gen.gi_frame is None)
    print("  gi_suspended:", gen.gi_suspended)

    # A generator that looks at its own state while it runs.
    def peek():
        yield inspect.getgeneratorstate(me)

    me = peek()
    print("inside:", next(me))


if __name__ == "__main__":
    main()
