"""Ask the desktop for light or dark and show what Sift picks."""

import os
import shutil

import darkdetect

from sift.gui.tk_app import detect_theme


def main() -> None:
    """Print what darkdetect sees on this machine."""
    print("darkdetect.theme():", darkdetect.theme())
    print("darkdetect.isDark():", darkdetect.isDark())
    print("detect_theme():", detect_theme())
    print("gsettings found:", shutil.which("gsettings") is not None)
    print("DISPLAY set:", "DISPLAY" in os.environ)
    print("XDG_CURRENT_DESKTOP:", os.environ.get("XDG_CURRENT_DESKTOP"))


if __name__ == "__main__":
    main()
