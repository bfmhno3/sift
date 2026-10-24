"""inspect: signature, getsource, getmembers, frames."""

import inspect

from sift.config import Config, Setting
from sift.scoring import bm25
from sift.search import Searcher


def where_am_i() -> str:
    """Return the name of the caller, found in the stack."""
    frame = inspect.currentframe()
    assert frame is not None and frame.f_back is not None
    return frame.f_back.f_code.co_name


def outer() -> str:
    return where_am_i()


def show_locals() -> dict[str, object]:
    """Return the caller's local variables."""
    frame = inspect.currentframe()
    assert frame is not None and frame.f_back is not None
    return dict(frame.f_back.f_locals)


def demo_locals() -> dict[str, object]:
    """Have two locals, then read them back through the frame."""
    answer = 42  # noqa: F841
    word = "hi"  # noqa: F841
    seen = show_locals()
    return {k: seen[k] for k in ("answer", "word")}


def main() -> None:
    """Print what inspect reports about Sift's own code."""
    print("-- signature")
    sig = inspect.signature(Searcher.__init__)
    for name, param in sig.parameters.items():
        print(f"  {name:11} {param.kind.name:20} {param.default!r}")
    print("  return:", sig.return_annotation)
    bound = inspect.signature(bm25).bind(3, 2, 100, 120.0, 8)
    bound.apply_defaults()
    print("  bind:", dict(bound.arguments))
    print("-- getsource (first 6 lines of bm25)")
    for line in inspect.getsource(bm25).splitlines()[:6]:
        print("  |", line)
    print("-- getmembers of Setting (public, by kind)")
    members = inspect.getmembers(Setting)
    for name, value in members:
        if name.startswith("_"):
            continue
        print(f"  {name:10} function={inspect.isfunction(value)}")
    print("-- getdoc, getmodule, ismethod")
    doc = inspect.getdoc(bm25) or ""
    module = inspect.getmodule(bm25)
    print("  ", doc.splitlines()[0])
    print("  ", module.__name__ if module else None)
    print("  ", inspect.ismethod(Config.limit.validate))
    print("  ", inspect.ismethod(Setting.validate))
    print("-- frames")
    print("  caller of where_am_i:", outer())
    print("  locals:", demo_locals())
    print("  stack depth in main:", len(inspect.stack()) - 1)
    print("  stack names:", [f.function for f in inspect.stack()][:2])


if __name__ == "__main__":
    main()
