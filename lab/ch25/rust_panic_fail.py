"""rust_panic_fail.py: a Rust panic becomes pyo3_runtime.PanicException.

The release build in src/sift has no way to panic on purpose: the
function panic_for_lab exists only when debug_assertions is on. This
file builds the debug library into rust/sift-rs/target/lab, copies it
to a temporary directory as _rs.so and imports it from there, so the
module of the repository is left alone.

PyO3 catches the unwinding panic at the boundary of every #[pyfunction]
and raises PanicException, which derives from BaseException, not from
Exception: `except Exception` does not stop it. The panic message is
printed twice, by the Rust panic hook (stderr) and in the traceback.
The file ends with the uncaught exception, so it must exit non-zero.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

CRATE = Path(__file__).resolve().parents[2] / "rust" / "sift-rs"
TARGET = CRATE / "target" / "lab"


def load_debug_build(into: Path) -> ModuleType:
    """Build the crate in debug mode and import it from into."""
    env = dict(os.environ, PYO3_BUILD_EXTENSION_MODULE="1")
    subprocess.run(
        ["cargo", "build", "--quiet", "--target-dir", str(TARGET)],
        cwd=CRATE,
        env=env,
        check=True,
    )
    library = into / "_rs.so"
    shutil.copy(TARGET / "debug" / "lib_rs.so", library)
    spec = importlib.util.spec_from_file_location("_rs", library)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        debug = load_debug_build(Path(tmp))
        print(f"debug build: {sorted(n for n in dir(debug) if n[0] != '_')}")
        print(f"tokenize still works: {debug.tokenize('c++ 中文')}")
        try:
            debug.panic_for_lab("boom from Rust")
        except Exception:
            print("caught by `except Exception`: no, this line never runs")
        except BaseException as error:
            cls = type(error)
            print(
                f"caught by `except BaseException`: "
                f"{cls.__module__}.{cls.__name__}: {error}"
            )
            print(f"is an Exception: {isinstance(error, Exception)}")
            print(f"mro: {[c.__name__ for c in cls.__mro__]}")
        sys.stdout.flush()
        print("now the same panic, uncaught:")
        sys.stdout.flush()
        debug.panic_for_lab("boom again, nobody catches it")


if __name__ == "__main__":
    main()
