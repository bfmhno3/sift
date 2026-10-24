"""Sift: a local full-text search engine for Markdown posts."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sift")
except PackageNotFoundError:
    # run from a source tree (PYTHONPATH=src) with no installed copy
    __version__ = "0.0.0+source"
