"""Measure where pack, grid and place put the same two widgets."""

import tkinter as tk


def box(master: tk.Misc, name: str, width: int, height: int) -> tk.Frame:
    """Return a Frame of a fixed size that keeps it."""
    frame = tk.Frame(master, width=width, height=height, name=name)
    frame.pack_propagate(False)
    frame.grid_propagate(False)
    return frame


def where(widget: tk.Misc) -> str:
    """Return x, y, width and height of widget as text."""
    return (
        f"x={widget.winfo_x():<4} y={widget.winfo_y():<4} "
        f"w={widget.winfo_width():<4} h={widget.winfo_height()}"
    )


def main() -> None:
    """Lay out a 400x200 area three ways and print the numbers."""
    root = tk.Tk()
    root.geometry("+0+0")

    area = box(root, "pack_area", 400, 200)
    area.pack()
    one = box(area, "one", 100, 40)
    two = box(area, "two", 100, 40)
    # expand=True shares the 160 px left over between the widgets
    # that expand: 'two' sits in the middle of them.
    one.pack(side="top", anchor="w")
    two.pack(side="top", fill="x", expand=True)
    root.update()
    print("pack top, 'two' fill=x expand=True")
    print("  one:", where(one))
    print("  two:", where(two))
    area.destroy()

    area = box(root, "grid_area", 400, 200)
    area.pack()
    one = box(area, "one", 100, 40)
    two = box(area, "two", 100, 40)
    area.columnconfigure(1, weight=1)
    one.grid(row=0, column=0)
    two.grid(row=0, column=1, sticky="ew", padx=10)
    root.update()
    print("grid, column 1 weight=1, 'two' sticky=ew padx=10")
    print("  one:", where(one))
    print("  two:", where(two))
    area.destroy()

    area = box(root, "place_area", 400, 200)
    area.pack()
    one = box(area, "one", 100, 40)
    two = box(area, "two", 100, 40)
    one.place(x=10, y=10)
    two.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
    root.update()
    print("place x=10 y=10 / relx=1 rely=1 anchor=se")
    print("  one:", where(one))
    print("  two:", where(two))

    # Two managers in one master would fight for ever; Tk refuses.
    area.destroy()
    area = box(root, "mixed_area", 400, 200)
    area.pack()
    box(area, "packed", 10, 10).pack()
    try:
        box(area, "gridded", 10, 10).grid()
    except tk.TclError as error:
        print("pack and grid in one master:", error)
    root.destroy()


if __name__ == "__main__":
    main()
