"""The attributes every module object carries."""

import importlib
import json
import types

import sift.analysis
import sift.search


def describe(module: types.ModuleType) -> None:
    """Print the import-system attributes of module."""
    spec = module.__spec__
    print(f"{module.__name__}")
    print(f"  __file__    = {getattr(module, '__file__', None)}")
    print(f"  __package__ = {module.__package__!r}")
    print(f"  __path__    = {getattr(module, '__path__', None)}")
    print(f"  __spec__    = {None if spec is None else spec.name}")
    if spec is not None:
        print(f"  loader      = {type(spec.loader).__name__}")
        print(f"  origin      = {spec.origin}")
        print(f"  cached      = {spec.cached}")


def main() -> None:
    """Describe this script, a stdlib module, a package and a module."""
    this = importlib.import_module("__main__")
    print("this script:")
    print(f"  __name__ = {__name__!r}")
    print(f"  __package__ = {__package__!r}")
    print(f"  __spec__ = {__spec__!r}")
    print(f"  __file__ = {this.__file__}")
    for module in (json, sift.analysis, sift.search, sift):
        describe(module)
    print("sift.__version__ =", sift.__version__)
    print("module dir() sample:", sorted(dir(json))[:6])
    print("modules are objects:", type(json), isinstance(json, object))


if __name__ == "__main__":
    main()
