"""Open a window with a few widgets, run the main loop, close it."""

import tkinter as tk
from tkinter import ttk


def main() -> None:
    """Show pack, grid and place side by side, then close itself."""
    root = tk.Tk()
    root.title("hello tk")
    root.geometry("640x240")

    clicks = tk.IntVar(root, value=0)

    def on_click() -> None:
        clicks.set(clicks.get() + 1)

    pack_box = ttk.LabelFrame(root, text="pack", padding=8)
    pack_box.pack(side="left", fill="both", expand=True)
    ttk.Label(pack_box, text="top").pack()
    button = ttk.Button(pack_box, text="click me", command=on_click)
    button.pack(pady=4)
    ttk.Label(pack_box, textvariable=clicks).pack(side="bottom")

    grid_box = ttk.LabelFrame(root, text="grid", padding=8)
    grid_box.pack(side="left", fill="both", expand=True)
    for row in range(2):
        for col in range(2):
            ttk.Label(grid_box, text=f"{row},{col}").grid(
                row=row, column=col, padx=6, pady=6
            )

    place_box = ttk.LabelFrame(root, text="place", padding=8)
    place_box.pack(side="left", fill="both", expand=True)
    ttk.Label(place_box, text="x=0.5").place(relx=0.5, rely=0.0, anchor="n")
    ttk.Label(place_box, text="corner").place(relx=1.0, rely=1.0, anchor="se")

    # invoke() is what a click does: it runs the command.
    root.after(100, lambda: [button.invoke() for _ in range(2)])
    root.after(500, root.destroy)
    count = len(root.winfo_children())
    root.mainloop()
    print("frames in the window:", count)
    print("clicks counted by the callback:", clicks.get())
    print("mainloop returned: the window is closed")


if __name__ == "__main__":
    main()
