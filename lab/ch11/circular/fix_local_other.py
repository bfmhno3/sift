"""The other half of fix 2: a top-level import of the first one."""

from circular.fix_local import own_value


def other_value() -> int:
    """Return a constant that does not need own_value."""
    return 10


def chained() -> int:
    """Call back through the top-level import."""
    return own_value()
