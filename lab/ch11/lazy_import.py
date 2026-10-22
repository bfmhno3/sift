"""Cost of an import, and two ways to postpone it."""

import statistics
import subprocess
import sys
import time

EAGER = "import asyncio"
FUNCTION = """\
def use():
    import asyncio
    return asyncio

"""
LAZY = """\
import importlib.util
import sys

spec = importlib.util.find_spec("asyncio")
loader = importlib.util.LazyLoader(spec.loader)
spec.loader = loader
module = importlib.util.module_from_spec(spec)
sys.modules["asyncio"] = module
loader.exec_module(module)
"""
LAZY_USED = LAZY + "module.run\n"
NOTHING = "pass"


def run_ms(code: str, repeat: int = 15) -> float:
    """Return the median wall time of ``python -c code`` in ms."""
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], check=True)
        times.append(time.perf_counter() - start)
    return statistics.median(times) * 1000


def main() -> None:
    """Time five variants in fresh interpreters."""
    variants = [
        ("nothing", NOTHING),
        ("eager import asyncio", EAGER),
        ("import inside a function, never called", FUNCTION),
        ("LazyLoader, never touched", LAZY),
        ("LazyLoader, one attribute read", LAZY_USED),
    ]
    base = run_ms(NOTHING)
    for label, code in variants:
        ms = run_ms(code)
        print(f"{ms:7.1f} ms  (+{ms - base:5.1f})  {label}")


if __name__ == "__main__":
    main()
