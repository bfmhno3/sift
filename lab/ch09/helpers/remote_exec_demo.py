"""Parent process: start a child and run code in it (sys.remote_exec).

This is the mechanism under ``python -m pdb -p PID`` (PEP 768). Under
Yama ptrace_scope 1 a process may attach to its own descendants only,
so the demo starts the target itself.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = """\
import time

counter = 0
while True:
    counter += 1
    time.sleep(0.05)
"""
INJECTED = """\
import os
import sys

main = sys.modules["__main__"]
print("injected: counter > 0:", main.counter > 0, flush=True)
os._exit(0)
"""


def main() -> None:
    """Start a child, inject a script into it, show what it prints."""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "inject.py"
        script.write_text(INJECTED, encoding="utf-8")
        with subprocess.Popen(
            [sys.executable, "-c", TARGET], stdout=subprocess.PIPE, text=True
        ) as child:
            try:
                time.sleep(0.5)
                print("parent: calling sys.remote_exec(child_pid, script)")
                sys.remote_exec(child.pid, str(script))
                out, _ = child.communicate(timeout=10)
                print("child printed:", out.strip())
                print("child exit status:", child.returncode)
            finally:
                child.kill()


if __name__ == "__main__":
    main()
