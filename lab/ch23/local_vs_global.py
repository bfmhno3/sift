"""Local names, globals, builtins and attributes: what a lookup costs.

``LOAD_FAST`` reads a slot of the frame. A global is a dict lookup,
though the specialized ``LOAD_GLOBAL_MODULE`` and
``LOAD_GLOBAL_BUILTIN`` cache the answer by dict version. An
attribute behind a dot (``math.sqrt``) adds one more lookup per
use. Binding the function to a local once, outside the loop, removes
both. The gain is small on 3.14 and the code gets harder to read: do
it in a measured hot loop, not everywhere.
"""

import dis
import math
import timeit
from math import sqrt

N = 200_000
REPEAT = 7


def attribute_in_loop(values: range) -> float:
    """Call math.sqrt through the module attribute."""
    total = 0.0
    for v in values:
        total += math.sqrt(v)
    return total


def global_in_loop(values: range) -> float:
    """Call sqrt, a global name of this module."""
    total = 0.0
    for v in values:
        total += sqrt(v)
    return total


def local_in_loop(values: range) -> float:
    """Bind math.sqrt to a local once."""
    root = math.sqrt
    total = 0.0
    for v in values:
        total += root(v)
    return total


def default_in_loop(values: range, root=math.sqrt) -> float:  # noqa: ANN001
    """Bind math.sqrt as a default argument, evaluated at def time."""
    total = 0.0
    for v in values:
        total += root(v)
    return total


def measure(func) -> float:  # noqa: ANN001
    """Return the best time of func over N values, in milliseconds."""
    values = range(N)
    func(values)
    runs = timeit.repeat(lambda: func(values), number=3, repeat=REPEAT)
    return min(runs) / 3 * 1e3


def loop_loads(func) -> list[str]:  # noqa: ANN001
    """Return the adaptive load opcodes between FOR_ITER and the jump."""
    names = [i.opname for i in dis.get_instructions(func, adaptive=True)]
    start = next(i for i, n in enumerate(names) if n.startswith("FOR_ITER"))
    stop = next(
        i for i, n in enumerate(names) if n.startswith("JUMP_BACKWARD")
    )
    return [n for n in names[start:stop] if n.startswith("LOAD")]


def main() -> None:
    """Time the four versions and show their lookup opcodes."""
    results = {
        f.__name__: measure(f)
        for f in (
            attribute_in_loop,
            global_in_loop,
            local_in_loop,
            default_in_loop,
        )
    }
    base = results["local_in_loop"]
    for name, ms in results.items():
        print(f"{name:<18} {ms:7.2f} ms  {ms / base:5.2f}x of local")
    for func in (attribute_in_loop, global_in_loop, local_in_loop):
        print(f"{func.__name__} loop loads: {', '.join(loop_loads(func))}")


if __name__ == "__main__":
    main()
