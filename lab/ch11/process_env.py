"""The process around the interpreter: argv, environ, exit, streams."""

import os
import subprocess
import sys


def exit_status(code: str) -> int:
    """Run ``python -c code`` and return its exit status."""
    done = subprocess.run([sys.executable, "-c", code], capture_output=True)
    return done.returncode


def main() -> None:
    """Show each piece of the process interface."""
    print("sys.argv:", [os.path.basename(arg) for arg in sys.argv])
    print("sys.orig_argv[:1]:", [os.path.basename(sys.orig_argv[0])])
    print("pid > 0, parent pid > 0:", os.getpid() > 0, os.getppid() > 0)

    print("SIFT_INDEX:", os.environ.get("SIFT_INDEX"))
    os.environ["SIFT_INDEX"] = "/tmp/demo-index"
    done = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ['SIFT_INDEX'])"],
        capture_output=True,
        text=True,
    )
    print("child sees:", done.stdout.strip())
    del os.environ["SIFT_INDEX"]
    print("os.environ is a", type(os.environ).__name__)
    print(
        "os.environ values are str:",
        all(isinstance(v, str) for v in os.environ.values()),
    )

    print("exit statuses of child interpreters:")
    for code in (
        "pass",
        "import sys; sys.exit(3)",
        "import sys; sys.exit('message')",
        "import sys; sys.exit(None)",
        "raise RuntimeError('boom')",
        "import os; os._exit(7)",
    ):
        print(f"  {exit_status(code):>3}  {code}")

    print("streams:")
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        print(
            f"  {stream.name:<9} fd={stream.fileno()} "
            f"encoding={stream.encoding} tty={stream.isatty()}"
        )
    print("to stdout")
    print("to stderr", file=sys.stderr)
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
