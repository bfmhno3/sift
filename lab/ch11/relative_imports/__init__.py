"""A two-module package that imports itself with dots."""

from .a import double

__all__ = ["double"]
