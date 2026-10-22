"""The other half of fix 1: it imports the first one as a module."""

from circular import fix_module


def other_value() -> int:
    """Return a constant; the import above is only a reference."""
    return 10


def both() -> int:
    """Call back into fix_module, after both are initialized."""
    return fix_module.own_value()
