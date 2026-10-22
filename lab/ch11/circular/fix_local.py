"""Fix 2: import inside the function that needs the name."""


def own_value() -> int:
    """Import the other module on the first call, not at load."""
    from circular.fix_local_other import other_value

    return other_value() + 1
