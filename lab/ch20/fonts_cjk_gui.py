"""Check which fonts Tk finds and who draws a CJK character."""

import os
import tkinter as tk
from tkinter import font


def main() -> None:
    """Print the families, a named font and the fallback for 所."""
    root = tk.Tk()
    families = set(font.families(root))
    print("FONTCONFIG_FILE set:", "FONTCONFIG_FILE" in os.environ)
    for name in ("Inter", "Noto Sans CJK SC", "JetBrains Mono"):
        print(f"family {name!r} known to Tk:", name in families)

    # A named font is a Tcl object: change it, and every widget that
    # uses it follows.
    body = font.Font(root, name="DemoBody", family="Inter", size=11)
    print("DemoBody:", body.actual("family"), body.actual("size"))
    print("named fonts include DemoBody:", "DemoBody" in font.names(root))

    # Inter has no CJK glyphs. Tk asks fontconfig for another family
    # per missing character; `font actual ... -- CHAR` names it.
    for char in ("a", "所", "é"):
        drawn_by = root.tk.call("font", "actual", "DemoBody", "--", char)
        print(f"{char!r} is drawn with {drawn_by[1]!r}")

    cjk = font.Font(root, family="Noto Sans CJK SC", size=11)
    print("width of 所有权 in Inter  :", body.measure("所有权"))
    print("width of 所有权 in Noto CJK:", cjk.measure("所有权"))
    print(
        "same width (the fallback is the CJK font):",
        body.measure("所有权") == cjk.measure("所有权"),
    )
    root.destroy()


if __name__ == "__main__":
    main()
