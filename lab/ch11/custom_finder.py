"""Two sys.meta_path finders: one logs imports, one serves a string."""

import importlib.abc
import importlib.util
import sys
from collections.abc import Sequence
from importlib.machinery import ModuleSpec
from types import ModuleType


class LoggingFinder(importlib.abc.MetaPathFinder):
    """Record the name of every module that is searched for."""

    def __init__(self) -> None:
        """Start with an empty log."""
        self.seen: list[str] = []

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Log fullname and decline, so the next finder runs."""
        self.seen.append(fullname)
        return None


class StringLoader(importlib.abc.Loader):
    """Build a module by running source text."""

    def __init__(self, source: str) -> None:
        """Keep the source."""
        self.source = source

    def exec_module(self, module: ModuleType) -> None:
        """Run the source in the module namespace."""
        exec(self.source, module.__dict__)


class StringFinder(importlib.abc.MetaPathFinder):
    """Answer for the names in a dict of sources."""

    def __init__(self, sources: dict[str, str]) -> None:
        """Keep the sources."""
        self.sources = sources

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Return a spec for a known name, else None."""
        if fullname in self.sources:
            loader = StringLoader(self.sources[fullname])
            return importlib.util.spec_from_loader(fullname, loader)
        return None


def main() -> None:
    """Install both finders and import through them."""
    logger = LoggingFinder()
    served = StringFinder({"virtual_hello": "GREETING = 'hi from a string'"})
    sys.meta_path.insert(0, logger)
    sys.meta_path.append(served)
    try:
        import colorsys  # noqa: F401

        import virtual_hello

        print("virtual_hello.GREETING:", virtual_hello.GREETING)
        print("its spec loader:", type(virtual_hello.__spec__.loader).__name__)
        print("its __file__:", getattr(virtual_hello, "__file__", None))
    finally:
        sys.meta_path.remove(logger)
        sys.meta_path.remove(served)
    print("names the logger saw:", logger.seen)
    print("default finders:")
    for finder in sys.meta_path:
        print("  ", finder.__name__ if hasattr(finder, "__name__") else finder)


if __name__ == "__main__":
    main()
