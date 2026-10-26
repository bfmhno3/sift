"""Is the experimental JIT of CPython 3.14 in this interpreter?

``sys._jit`` (3.14) tells whether the interpreter was built with the
JIT (``--enable-experimental-jit``) and whether it is switched on
(the ``PYTHON_JIT`` environment variable). The same check also names
the other build options that change speed.
"""

import sys
import sysconfig


def main() -> None:
    """Print the JIT status and the interpreter build options."""
    print(sys.version)
    jit = getattr(sys, "_jit", None)
    if jit is None:
        print("sys._jit: missing (Python older than 3.14)")
    else:
        available = jit.is_available()
        print(f"sys._jit.is_available(): {available}")
        print(f"sys._jit.is_enabled():   {jit.is_enabled()}")
        if not available:
            print("JIT unavailable: this build has no experimental JIT")
    args = sysconfig.get_config_var("CONFIG_ARGS") or ""
    options = [a.strip("'") for a in args.split() if "--with-lto" in a]
    print("tail-call interpreter option:", "tail-call" in args)
    print("lto option:", options or "none")
    print("GIL enabled:", sys._is_gil_enabled())


if __name__ == "__main__":
    main()
