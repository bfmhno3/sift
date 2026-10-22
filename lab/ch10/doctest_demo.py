"""Run the doctests of two Sift modules, then one that fails.

``python -m doctest`` and ``pytest --doctest-modules`` run the same
``>>>`` examples. Here ``doctest.testmod`` does it from a script and
reports how many examples ran.
"""

import doctest

import sift.query.ast
import sift.scoring
import sift.snippet

# BAD: the expected output below is wrong on purpose, so doctest
# prints a failure report instead of staying silent.
BROKEN = """
>>> 1 + 1
3
"""

ELLIPSIS = """
Directives change how output is compared:

>>> list(range(20))  # doctest: +ELLIPSIS
[0, 1, ..., 19]
>>> print("a   b\\n c")  # doctest: +NORMALIZE_WHITESPACE
a b
c
>>> list(range(1000))  # doctest: +SKIP
whatever
"""


def main() -> None:
    """Run the module doctests, then the two string examples."""
    for module in (sift.scoring, sift.snippet, sift.query.ast):
        result = doctest.testmod(module)
        print(f"{module.__name__}: {result}")
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(verbose=False)
    for name, source in (("directives", ELLIPSIS), ("broken", BROKEN)):
        test = parser.get_doctest(source, {}, name, None, 0)
        print(f"--- {name}: {len(test.examples)} examples")
        runner.run(test)
    print(f"summary: {runner.summarize(verbose=False)}")


if __name__ == "__main__":
    main()
