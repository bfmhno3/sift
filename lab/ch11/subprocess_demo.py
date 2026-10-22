"""subprocess.run: capture, check, timeout, input and quoting."""

import shlex
import subprocess
import sys


def main() -> None:
    """Run small commands and show what comes back."""
    done = subprocess.run(
        [sys.executable, "-m", "sift", "--version"],
        capture_output=True,
        text=True,
    )
    print("returncode:", done.returncode)
    print("stdout:", repr(done.stdout))
    print("args:", [done.args[0].rsplit("/", 1)[-1], *done.args[1:]])

    try:
        subprocess.run(
            [sys.executable, "-c", "import sys; sys.exit(3)"], check=True
        )
    except subprocess.CalledProcessError as error:
        print("check=True raised:", error.returncode, type(error).__name__)

    try:
        subprocess.run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.3,
        )
    except subprocess.TimeoutExpired as error:
        print("timeout raised after", error.timeout, "s")

    done = subprocess.run(
        [sys.executable, "-c", "print(input().upper())"],
        input="from stdin\n",
        capture_output=True,
        text=True,
    )
    print("input=:", done.stdout.strip())

    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print("stderr merged:", done.stdout.split())

    name = "my notes; echo INJECTED"
    # BAD: a string with shell=True runs whatever the name contains
    unsafe = subprocess.run(
        f"echo {name}", shell=True, capture_output=True, text=True
    )
    print("shell=True with a bad name:", unsafe.stdout.split("\n")[:2])
    safe = subprocess.run(["echo", name], capture_output=True, text=True)
    print("argument list:", safe.stdout.strip())
    print("shlex.quote:", shlex.quote(name))
    print("shlex.split:", shlex.split("vim -c 'set ft=md' note.md"))
    quoted = subprocess.run(
        f"echo {shlex.quote(name)}",
        shell=True,
        capture_output=True,
        text=True,
    )
    print("quoted for the shell:", quoted.stdout.strip())

    missing = None
    try:
        subprocess.run(["no-such-program-sift"])
    except FileNotFoundError as error:
        missing = error
    print("missing program:", type(missing).__name__, missing)


if __name__ == "__main__":
    main()
