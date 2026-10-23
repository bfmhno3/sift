"""signal: handlers, KeyboardInterrupt, ignoring, alarm."""

import os
import signal
import subprocess
import sys
import time
from types import FrameType


def main() -> None:
    """Send signals to this process and to a child."""
    received: list[str] = []

    def on_sigint(signum: int, frame: FrameType | None) -> None:
        received.append(signal.Signals(signum).name)

    print("default SIGINT handler:", signal.getsignal(signal.SIGINT).__name__)
    try:
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(1)
    except KeyboardInterrupt:
        print("default handler raised KeyboardInterrupt")

    previous = signal.signal(signal.SIGINT, on_sigint)
    os.kill(os.getpid(), signal.SIGINT)
    print("handler ran:", received)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    os.kill(os.getpid(), signal.SIGINT)
    print("SIGINT ignored, still running")
    signal.signal(signal.SIGINT, previous)

    def on_alarm(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError("alarm fired")

    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(1)
    try:
        time.sleep(5)
    except TimeoutError as error:
        print("alarm interrupted sleep:", error)
    finally:
        signal.alarm(0)

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    child.send_signal(signal.SIGTERM)
    code = child.wait()
    print("child exit status after SIGTERM:", code)
    print("that is", signal.Signals(-code).name)

    code = (
        "import os, signal, sift.cli as cli;"
        "cli.run_stats = lambda a: os.kill(os.getpid(), signal.SIGINT);"
        "cli.main(['stats'])"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True)
    print("sift on Ctrl-C:", done.returncode, done.stderr.decode().strip())

    try:
        signal.signal(signal.SIGKILL, on_sigint)
    except OSError as error:
        print("SIGKILL cannot be caught:", error)


if __name__ == "__main__":
    main()
