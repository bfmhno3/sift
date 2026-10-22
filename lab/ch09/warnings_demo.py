"""warnings: warn, filters, categories and DeprecationWarning."""

import warnings
from warnings import deprecated


def old_search(query: str) -> str:
    """Call warnings.warn the way a library does."""
    warnings.warn("old_search is slow", DeprecationWarning, stacklevel=2)
    return query


@deprecated("use Searcher.search instead")
def legacy(query: str) -> str:
    """Return query; the decorator warns on every call (3.13+)."""
    return query


def show(caught: list[warnings.WarningMessage]) -> None:
    """Print category and message of each recorded warning."""
    if not caught:
        print("  (nothing recorded)")
    for item in caught:
        print(f"  {item.category.__name__}: {item.message}")


def main() -> None:
    """Show which warnings appear and why."""
    print("default filters (first three):")
    for entry in warnings.filters[:3]:
        print("  ", entry[0], entry[2].__name__, entry[3] or "")

    print("-- default filters: who sees a DeprecationWarning?")
    with warnings.catch_warnings(record=True) as caught:
        warnings.warn("from __main__", DeprecationWarning, stacklevel=1)
        warnings.warn_explicit(
            "from another module",
            DeprecationWarning,
            filename="library.py",
            lineno=1,
            module="library",
        )
    show(caught)

    print("-- the default action shows a location once")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        for _ in range(3):
            warnings.warn("careful", UserWarning, stacklevel=1)
    show(caught)

    print("-- simplefilter('always')")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_search("x")
        old_search("x")
    show(caught)

    print("-- simplefilter('ignore')")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("ignore")
        old_search("x")
    show(caught)

    print("-- simplefilter('error') turns a warning into an exception")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            old_search("x")
        except DeprecationWarning as exc:
            print("  raised DeprecationWarning:", exc)

    print("-- filterwarnings by message and category")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", message="old_.*")
        old_search("x")
        warnings.warn("other", DeprecationWarning, stacklevel=1)
    show(caught)

    print("-- @warnings.deprecated")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy("x")
    show(caught)

    print("-- custom category")

    class SlowQueryWarning(UserWarning):
        """A warning that a caller can filter on its own."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn("took 2 s", SlowQueryWarning, stacklevel=1)
    show(caught)


if __name__ == "__main__":
    main()
