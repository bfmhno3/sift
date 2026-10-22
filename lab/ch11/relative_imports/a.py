"""Module a: one relative import and one absolute import."""

import relative_imports.b

from .b import OFFSET

ABSOLUTE_OFFSET = relative_imports.b.OFFSET


def double(value: int) -> int:
    """Return twice value plus the offset that b defines."""
    return value * 2 + OFFSET
