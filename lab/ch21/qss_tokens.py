"""Print the style sheet generated for both themes.

The whole look of the window is one string made from the tokens in
``sift.gui.qt.theme``; a theme switch swaps the string.
"""

from sift.gui.qt.theme import DARK, LIGHT, generate_qss


def main() -> None:
    for tokens in (LIGHT, DARK):
        qss = generate_qss(tokens)
        print(
            f"/* ===== {tokens.name}: {len(qss.splitlines())} lines ===== */"
        )
        print(qss)


if __name__ == "__main__":
    main()
