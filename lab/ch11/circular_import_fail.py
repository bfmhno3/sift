"""Circular imports: two fixes that work and one that fails."""

import sys


def show_fix_module() -> None:
    """Fix 1: each module imports the other as a module."""
    from circular import fix_module, fix_module_other

    print("fix 1 own_value:", fix_module.own_value())
    print("fix 1 both:", fix_module_other.both())


def show_fix_local() -> None:
    """Fix 2: one side imports inside the function."""
    from circular import fix_local, fix_local_other

    print("fix 2 own_value:", fix_local.own_value())
    print("fix 2 chained:", fix_local_other.chained())


def main() -> None:
    """Run both fixes, then the import that fails."""
    show_fix_module()
    show_fix_local()
    print("half-built modules left behind:")
    for name in ("circular.a", "circular.b"):
        print(" ", name, name in sys.modules)
    # BAD: a imports b at the top, and b imports a back at the top
    # error: ImportError: cannot import name 'a_value' from partially
    # initialized module 'circular.a' (most likely due to a circular
    # import) (/path/to/lab/ch11/circular/a.py)
    try:
        import circular.a
    except ImportError:
        # the failed import removed both half-built modules again
        for name in ("circular.a", "circular.b"):
            print(f"after the failure, {name} in sys.modules:", end=" ")
            print(name in sys.modules)
        raise

    print(circular.a.a_value)


if __name__ == "__main__":
    main()
