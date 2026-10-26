"""Shapes that do not broadcast raise ValueError (on purpose)."""

import numpy as np


def main() -> None:
    """Add a (3,) array to a (4,) array: no common shape."""
    left = np.arange(3)
    right = np.arange(4)
    print(f"left {left.shape}, right {right.shape}")
    # ValueError: operands could not be broadcast together
    print(left + right)


if __name__ == "__main__":
    main()
