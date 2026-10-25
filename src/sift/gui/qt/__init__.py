"""The PySide6 window of Sift: ``sift gui``.

``theme`` holds the design tokens and the one QSS string built from
them, ``model`` and ``delegate`` the result list, ``worker`` the
search on a ``QThreadPool``, ``window`` the main window and ``app``
the entry point. Nothing is imported here: ``import sift.gui.qt``
does not load Qt, and neither do ``sift --version`` or any command
other than ``sift gui``.
"""
