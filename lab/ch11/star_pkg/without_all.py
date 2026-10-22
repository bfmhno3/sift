"""A module without __all__: star import takes every public name."""

import json

CONSTANT = 7


def helper() -> str:
    """Return a marker."""
    return json.dumps("helper")


def _private() -> str:
    """Return a marker; the name starts with an underscore."""
    return "private"
