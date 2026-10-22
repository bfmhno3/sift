"""The same tokenizer test in unittest style and in pytest style.

pytest collects plain functions and uses the bare ``assert``; unittest
needs a TestCase subclass and one ``assert*`` method per comparison.
This file runs the unittest version with ``unittest.main(exit=False)``
so the script can go on and print the pytest version next to it.
"""

import unittest

from sift.analysis import tokenize


class TokenizeTests(unittest.TestCase):
    """The unittest version: a class, setUp and assert methods."""

    def setUp(self) -> None:
        """Run before every test method."""
        self.text = "Rust 所有权 and C++"

    def test_terms(self) -> None:
        self.assertEqual(
            tokenize(self.text), ["rust", "所有", "有权", "and", "c++"]
        )

    def test_empty(self) -> None:
        self.assertEqual(tokenize(""), [])

    def test_many_inputs_with_subtest(self) -> None:
        cases = {"ABC": ["abc"], "ﬁ": ["fi"], "索": ["索"], "...": []}
        for text, terms in cases.items():
            with self.subTest(text=text):
                self.assertEqual(tokenize(text), terms)

    def test_a_type_error(self) -> None:
        with self.assertRaises(TypeError):
            tokenize(None)  # type: ignore[arg-type]


# The pytest version of the first test: a function, a plain assert.
# On failure pytest rewrites the assert to show both sides.
def test_terms() -> None:
    text = "Rust 所有权 and C++"
    assert tokenize(text) == ["rust", "所有", "有权", "and", "c++"]


def main() -> None:
    """Run the TestCase with unittest, the function by hand."""
    program = unittest.main(exit=False, argv=["unittest_demo"], verbosity=2)
    print(f"unittest: wasSuccessful() = {program.result.wasSuccessful()}")
    print(f"unittest: tests run = {program.result.testsRun}")
    test_terms()
    print("pytest-style function called by hand: ok")


if __name__ == "__main__":
    main()
