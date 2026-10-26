"""Broadcasting rules, ufuncs and the random generator."""

import numpy as np


def main() -> None:
    """Combine arrays of different shapes without a Python loop."""
    column = np.arange(3).reshape(3, 1)
    row = np.arange(4)
    print(f"column shape {column.shape}, row shape {row.shape}")
    table = column * 10 + row
    print(f"column * 10 + row -> shape {table.shape}")
    print(table.tolist())

    # rule: align shapes on the right; a 1 or a missing axis stretches
    for left, right in [((3, 1), (4,)), ((2, 3, 4), (3, 1)), ((5,), (1,))]:
        shape = np.broadcast_shapes(left, right)
        print(f"{left} with {right} -> {shape}")

    rng = np.random.default_rng(1234)
    data = rng.normal(loc=10.0, scale=2.0, size=(5, 3))
    centered = data - data.mean(axis=0)
    print(f"column means after centering: {centered.mean(axis=0).round(12)}")
    scaled = centered / centered.std(axis=0)
    print(f"column std after scaling: {scaled.std(axis=0).round(12)}")

    # ufuncs work element by element and take out= and where=
    x = np.array([1.0, 4.0, 9.0, -1.0])
    out = np.zeros_like(x)
    np.sqrt(x, out=out, where=x >= 0)
    print(f"sqrt where x >= 0: {out.tolist()}")
    print(f"np.add.reduce(x) = {np.add.reduce(x)}, x.sum() = {x.sum()}")
    print(f"np.maximum.accumulate: {np.maximum.accumulate(x).tolist()}")


if __name__ == "__main__":
    main()
