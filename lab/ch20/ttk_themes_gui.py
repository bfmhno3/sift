"""List the ttk themes before and after sv-ttk, and what a theme is."""

import tkinter as tk
from tkinter import ttk

import sv_ttk


def main() -> None:
    """Print theme names, the layout of a button and style lookups."""
    root = tk.Tk()
    style = ttk.Style(root)
    print("themes at start:", sorted(style.theme_names()))
    print("current:", style.theme_use())

    sv_ttk.set_theme("light", root)
    print("themes after sv-ttk:", sorted(style.theme_names()))
    print(
        "current:", style.theme_use(), "-> sv_ttk says", sv_ttk.get_theme(root)
    )

    # A theme is a set of elements plus a layout per widget class.
    print("layout of TButton:", style.layout("TButton"))
    print("layout of Accent.TButton:", style.layout("Accent.TButton"))
    print("padding of TButton:", style.lookup("TButton", "padding"))
    print("font of TLabel:", style.lookup("TLabel", "font"))

    # A style is the same widget class with other options: here the
    # derived style "Accent.TButton" comes from the theme file.
    print(
        "has Accent.TButton:",
        "Accent.TButton" in style.element_names()
        or bool(style.layout("Accent.TButton")),
    )

    # The colors live in Tcl arrays of the theme.
    for theme in ("light", "dark"):
        array = f"::ttk::theme::sv_{theme}::colors"
        pairs = {
            key: root.tk.eval(f"set {array}(-{key})")
            for key in ("bg", "fg", "accent")
        }
        print(f"sv_{theme} colors:", pairs)

    sv_ttk.set_theme("dark", root)
    print("after set_theme('dark'):", sv_ttk.get_theme(root))
    root.destroy()


if __name__ == "__main__":
    main()
