"""Watch a StringVar, key and mouse events, and a virtual event."""

import tkinter as tk
from tkinter import ttk


def main() -> None:
    """Drive an Entry with generated events and print what arrives."""
    root = tk.Tk()
    root.geometry("320x120+0+0")
    text = tk.StringVar(root)
    entry = ttk.Entry(root, textvariable=text)
    entry.pack(padx=16, pady=16)
    log: list[str] = []

    # A variable is a Tcl variable; trace_add runs a callback when
    # it is written, whoever wrote it.
    def on_write(name: str, index: str, mode: str) -> None:
        log.append(f"trace {mode}: {text.get()!r}")

    text.trace_add("write", on_write)

    def on_key(event: tk.Event[ttk.Entry]) -> None:
        log.append(
            f"key keysym={event.keysym} char={event.char!r} "
            f"type={event.type.name}"
        )

    def on_return(event: tk.Event[ttk.Entry]) -> str:
        log.append(f"Return in {event.widget}, text={text.get()!r}")
        return "break"  # stop here: no class binding, no later tag

    def on_click(event: tk.Event[ttk.Entry]) -> None:
        log.append(f"click x={event.x} y={event.y} num={event.num}")

    def on_virtual(event: tk.Event[ttk.Entry]) -> None:
        log.append(f"virtual {event.type.name} on {event.widget}")

    entry.bind("<KeyPress>", on_key)
    entry.bind("<Return>", on_return)
    entry.bind("<Button-1>", on_click)
    # A virtual event is a name for a set of real events.
    # Tk runs only the most specific binding of a tag: <Return> is
    # bound to on_return, so <<Search>> does not fire for it.
    root.event_add("<<Search>>", "<Return>", "<Control-s>")
    entry.bind("<<Search>>", on_virtual)

    root.update()
    entry.focus_force()
    root.update()
    for char in "ab":
        entry.event_generate(f"<KeyPress-{char}>")
    entry.event_generate("<Button-1>", x=5, y=6)
    entry.event_generate("<Return>")
    entry.event_generate("<<Search>>")
    text.set("set from Python")
    entry.event_generate("<Control-s>")
    root.update()

    for line in log:
        print(line)
    print("bindtags:", entry.bindtags())
    root.destroy()


if __name__ == "__main__":
    main()
