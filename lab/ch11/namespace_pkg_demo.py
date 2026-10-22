"""A namespace package: one name, two directories, no __init__.py."""

import sys
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    """Import one module from each directory under one package name."""
    for part in ("one", "two"):
        sys.path.append(str(HERE / "namespace" / part))
    import nspkg
    from nspkg import alpha, beta

    print("alpha lives in:", alpha.WHERE)
    print("beta lives in:", beta.WHERE)
    print("package type:", type(nspkg).__name__)
    print("__file__:", getattr(nspkg, "__file__", None))
    print("__path__ is a", type(nspkg.__path__).__name__)
    for entry in nspkg.__path__:
        print("  ", Path(entry).relative_to(HERE))
    print("loader:", nspkg.__spec__.loader)


if __name__ == "__main__":
    main()
