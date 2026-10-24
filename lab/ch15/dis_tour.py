"""dis: the bytecode of a comprehension, LOAD_FAST vs LOAD_GLOBAL."""

import dis
from collections.abc import Callable

SCALE = 3


def squares(numbers: list[int]) -> list[int]:
    """A comprehension: the loop variable is a local."""
    return [n * n for n in numbers]


def scaled_global(numbers: list[int]) -> list[int]:
    """Reads the global SCALE on every iteration."""
    return [n * SCALE for n in numbers]


def scaled_local(numbers: list[int]) -> list[int]:
    """Copies SCALE into a local first."""
    scale = SCALE
    return [n * scale for n in numbers]


def opnames(func: Callable[..., object]) -> list[str]:
    """Return the opcode names of a function, in order."""
    return [i.opname for i in dis.get_instructions(func)]


def main() -> None:
    """Disassemble and compare."""
    print("-- dis.dis(squares): 3.12+ inlines the comprehension")
    dis.dis(squares)
    print("-- code objects nested in squares:")
    nested = [c for c in squares.__code__.co_consts if hasattr(c, "co_name")]
    print("  ", [c.co_name for c in nested])
    print("-- global vs local")
    for func in (scaled_global, scaled_local):
        names = opnames(func)
        loop = names[names.index("FOR_ITER") : names.index("JUMP_BACKWARD")]
        print(f"  {func.__name__:13} loop body: {loop}")
    print("-- dis.dis(scaled_global)")
    dis.dis(scaled_global)
    print("-- co_varnames / co_names")
    print(
        "  squares      :",
        squares.__code__.co_varnames,
        squares.__code__.co_names,
    )
    print(
        "  scaled_global:",
        scaled_global.__code__.co_varnames,
        scaled_global.__code__.co_names,
    )
    print("-- dis of a string, without a def")
    dis.dis("a + b * 2")


if __name__ == "__main__":
    main()
