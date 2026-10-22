"""sys.modules: import twice, delete the entry, reload."""

import importlib
import sys
import tempfile
from pathlib import Path

SOURCE = """\
import itertools

counter = itertools.count(1)
print("  (module body runs)")
VALUE = 1
"""


def main() -> None:
    """Show that import runs the body once and reload runs it again."""
    import json
    import json as again

    print("same object:", json is again)
    print("cached under:", sys.modules["json"] is json)

    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "cached_mod.py").write_text(SOURCE)
        sys.path.insert(0, tmp)
        try:
            print("first import:")
            import cached_mod

            print("second import:")
            import cached_mod as second

            print("same object:", cached_mod is second)
            Path(tmp, "cached_mod.py").write_text(
                SOURCE.replace("VALUE = 1", "VALUE = 22")
            )
            print("VALUE before reload:", cached_mod.VALUE)
            importlib.invalidate_caches()
            print("reload:")
            reloaded = importlib.reload(cached_mod)
            print("reload returns the same module:", reloaded is cached_mod)
            print("VALUE after reload:", cached_mod.VALUE)

            print("del sys.modules entry, import again:")
            first = sys.modules.pop("cached_mod")
            import cached_mod as fresh

            print("new object:", fresh is not first)
        finally:
            sys.path.remove(tmp)
            sys.modules.pop("cached_mod", None)

    sys.modules["json"] = None  # type: ignore[assignment]
    try:
        import json as blocked  # noqa: F401
    except ImportError as error:
        print("None in sys.modules:", error)
    finally:
        sys.modules["json"] = json


if __name__ == "__main__":
    main()
