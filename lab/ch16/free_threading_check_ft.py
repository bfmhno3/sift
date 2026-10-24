"""Is this interpreter free-threaded, and does it stay that way?"""

import subprocess
import sys
import sysconfig


def gil_state(*args: str) -> str:
    """Return sys._is_gil_enabled() of a child started with args."""
    code = "import sys; print(sys._is_gil_enabled())"
    done = subprocess.run(
        [sys.executable, *args, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def main() -> None:
    """Print the facts that tell a free-threaded build apart."""
    print("version         :", sys.version.split()[0])
    print("abiflags        :", repr(sys.abiflags))
    print("Py_GIL_DISABLED :", sysconfig.get_config_var("Py_GIL_DISABLED"))
    print("_is_gil_enabled :", sys._is_gil_enabled())
    print("-- importing extension modules does not turn the GIL back on")
    for name in ("sqlite3", "decimal", "zlib", "ssl", "unicodedata", "mmap"):
        __import__(name)
        print(f"  after import {name:<12}:", sys._is_gil_enabled())
    print("-- PYTHON_GIL and -X gil switch it for one run")
    print("  default      :", gil_state())
    print("  -X gil=1     :", gil_state("-X", "gil=1"))
    print("  -X gil=0     :", gil_state("-X", "gil=0"))
    print(
        "switch interval:", sys.getswitchinterval(), "s (unused without a GIL)"
    )


if __name__ == "__main__":
    main()
