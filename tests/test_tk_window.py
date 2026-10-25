"""Run the display tests of ``tests/tk_display`` under Xvfb.

The window tests need a display. They live in a directory that a
normal run skips (see conftest.py), and this test starts pytest on it
inside ``xvfb-run``, a virtual X server: the same result everywhere,
and no window on the screen of the developer. It is skipped when
tkinter, sv-ttk, darkdetect or xvfb-run is missing.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def test_window_tests_pass_under_xvfb() -> None:
    for name in ("tkinter", "sv_ttk", "darkdetect"):
        if importlib.util.find_spec(name) is None:
            pytest.skip(f"{name} is not installed")
    xvfb = shutil.which("xvfb-run")
    if xvfb is None:
        pytest.skip("xvfb-run is not installed")
    env = dict(os.environ, SIFT_TK_DISPLAY_TESTS="1")
    env.pop("DISPLAY", None)
    done = subprocess.run(
        [
            xvfb,
            "-a",
            "-s",
            "-screen 0 1100x700x24",
            sys.executable,
            "-m",
            "pytest",
            str(HERE / "tk_display"),
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-rs",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        cwd=HERE.parent,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "skipped" not in done.stdout, done.stdout
