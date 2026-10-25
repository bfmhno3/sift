"""Talk to the Tcl interpreter that lives inside the Tk object."""

import re
import tkinter as tk
from tkinter import ttk


def main() -> None:
    """Run Tcl by hand, show widget names and callback commands."""
    root = tk.Tk()
    interp = root.tk
    print("type of root.tk:", type(interp).__name__)

    print("eval 'expr 6*7'      ->", interp.eval("expr 6*7"))
    print("call set x 5         ->", interp.call("set", "x", 5))
    print("eval 'set x'         ->", interp.eval("set x"))
    print("call info patchlevel ->", interp.call("info", "patchlevel"))
    print("windowingsystem      ->", interp.call("tk", "windowingsystem"))

    # Every widget is a Tcl command named after its path.
    frame = ttk.Frame(root)
    button = ttk.Button(frame, text="hi")
    print("str(root)  :", str(root))
    print("str(frame) :", str(frame))
    print("str(button):", str(button))
    print("Tcl sees   :", interp.eval("winfo children ."))
    print("class      :", interp.call("winfo", "class", str(button)))

    # A widget made by Tcl has no Python object until you ask for one.
    interp.eval("ttk::label .made_in_tcl -text from-tcl")
    print("children   :", sorted(root.children))
    print("Tcl children:", interp.eval("winfo children ."))

    # The button is a command: Python can call it like Tcl would.
    interp.call(str(button), "configure", "-text", "changed")
    print("cget text  :", button.cget("text"))

    # A Python callback becomes a Tcl command with a generated name.
    def callback() -> None:
        print("callback ran")

    name = root.register(callback)
    print("command name:", re.sub(r"\d+", "N", name))
    interp.eval(name)
    print("exists in Tcl:", interp.eval(f"llength [info commands {name}]"))

    # Values cross the border as strings (or Tcl objects).
    root.setvar("answer", 42)
    print("getvar     :", repr(root.getvar("answer")))
    print("tk.call int:", repr(interp.call("expr", "6*7")))
    root.destroy()


if __name__ == "__main__":
    main()
