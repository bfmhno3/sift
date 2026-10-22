"""A module whose __all__ lists the public names."""

import json

__all__ = ["public", "CONSTANT"]

CONSTANT = 42


def public() -> str:
    """Return a marker; it is in __all__."""
    return "public"


def helper() -> str:
    """Return a marker; it is not in __all__."""
    return json.dumps("helper")


def _private() -> str:
    """Return a marker; the name starts with an underscore."""
    return "private"
