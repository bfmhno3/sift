"""Where imports are looked for: sys.path, hooks and PYTHONPATH."""

import os
import subprocess
import sys
from pathlib import Path


def short(entry: str) -> str:
    """Return entry with the home directory shortened to ~."""
    home = str(Path.home())
    return "~" + entry[len(home) :] if entry.startswith(home) else entry


def main() -> None:
    """Print sys.path, then show what PYTHONPATH and -P change."""
    print("sys.path[0] is the script directory:", short(sys.path[0]))
    print("entries:")
    for entry in sys.path:
        print("  ", short(entry))
    print("path hooks:", [hook.__name__ for hook in sys.path_hooks])
    print("importer cache keys:", len(sys.path_importer_cache) > 0)

    code = "import sys; print(sys.path[:2])"
    env = {**os.environ, "PYTHONPATH": "/tmp/first:/tmp/second"}
    for label, argv in [
        ("PYTHONPATH", [sys.executable, "-c", code]),
        ("-P (safe path)", [sys.executable, "-P", "-c", code]),
        ("-I (isolated)", [sys.executable, "-I", "-c", code]),
    ]:
        done = subprocess.run(
            argv, env=env, capture_output=True, text=True, check=True
        )
        print(f"{label:>15}: {done.stdout.strip()}")

    sys.path.insert(0, "/tmp/inserted")
    print("after insert:", sys.path[0])
    sys.path.remove("/tmp/inserted")


if __name__ == "__main__":
    main()
