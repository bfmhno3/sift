"""Fix 1: import the module, read the name when it is needed."""

from circular import fix_module_other


def own_value() -> int:
    """Return a value that depends on the other module."""
    return fix_module_other.other_value() + 1
