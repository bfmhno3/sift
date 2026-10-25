"""Sift: a local full-text search engine for Markdown posts."""


def __getattr__(name: str) -> str:
    """Return ``sift.__version__``, read from the metadata on first use.

    ``importlib.metadata`` costs about 30 ms to import, which every
    ``sift`` command would pay at start-up for a number that only
    ``--version`` and the web server print.
    """
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib.metadata import PackageNotFoundError, version

    try:
        found = version("sift")
    except PackageNotFoundError:
        # run from a source tree (PYTHONPATH=src) with no installed copy
        found = "0.0.0+source"
    globals()["__version__"] = found
    return found
