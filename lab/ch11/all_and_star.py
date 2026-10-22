"""__all__ and ``from module import *``."""

import star_pkg.with_all
import star_pkg.without_all

import sift.analysis


def star_names(module: str) -> list[str]:
    """Return the names that ``from module import *`` binds."""
    namespace: dict[str, object] = {}
    exec(f"from {module} import *", namespace)
    namespace.pop("__builtins__")
    return sorted(namespace)


def main() -> None:
    """Compare a module with __all__ and one without."""
    print("with __all__:   ", star_pkg.with_all.__all__)
    print("star imports:   ", star_names("star_pkg.with_all"))
    print("without __all__:", hasattr(star_pkg.without_all, "__all__"))
    print("star imports:   ", star_names("star_pkg.without_all"))
    print("sift.analysis.__all__ has", len(sift.analysis.__all__), "names")
    print("explicit import still reaches helper:")
    from star_pkg.with_all import helper

    print("  ", helper())


if __name__ == "__main__":
    main()
