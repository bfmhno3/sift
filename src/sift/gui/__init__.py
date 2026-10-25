"""Graphical front ends of Sift.

``sift.gui.controller`` holds what every window does and imports no
toolkit. ``sift.gui.tk_app`` is the tkinter window; it needs the
``gui`` extra (``sv-ttk``, ``darkdetect``) and a Python built with
tkinter. Nothing is imported here, so ``import sift.gui`` is free.
"""
