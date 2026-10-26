"""The adaptive interpreter (PEP 659): bytecode that specializes.

``dis.dis(f, adaptive=True)`` shows the instructions as the
interpreter holds them. A fresh function has the generic ones
(``BINARY_OP``); after some calls with the same types the
interpreter replaces them with specialized ones
(``BINARY_OP_ADD_INT``) that skip the type dispatch. A call with
other types fails the guard and the instruction goes back to the
generic form until it is specialized again.
"""

import dis
from collections.abc import Callable

WARMUP = 2000


def add(a, b):
    """Add two values: the types decide the specialization."""
    return a + b


def sum_to(n: int) -> int:
    """Add the integers below n in a loop."""
    total = 0
    for i in range(n):
        total = total + i
    return total


def names(code: Callable[..., object]) -> list[str]:
    """Return the adaptive opcode names of code, in order."""
    return [ins.opname for ins in dis.get_instructions(code, adaptive=True)]


def show(title: str, code: Callable[..., object]) -> None:
    """Print the adaptive disassembly of code under a title."""
    print(f"--- {title}")
    dis.dis(code, adaptive=True)


def main() -> None:
    """Disassemble before and after the warm-up."""
    before = names(sum_to)
    show("sum_to before any call", sum_to)
    for _ in range(WARMUP):
        sum_to(10)
    after = names(sum_to)
    show(f"sum_to after {WARMUP} calls with ints", sum_to)
    changed = sorted({n for n in after if n not in before})
    print("opcodes that appeared:", ", ".join(changed))

    print()
    show("add before any call", add)
    for _ in range(WARMUP):
        add(1, 2)
    print(f"add after {WARMUP} calls with ints:", names(add))
    for _ in range(WARMUP):
        add(1.5, 2.5)
    print(f"add after {WARMUP} calls with floats:", names(add))
    for _ in range(WARMUP):
        add("a", "b")
    print(f"add after {WARMUP} calls with str:", names(add))


if __name__ == "__main__":
    main()
