"""The memory model of ndarray: dtype, shape, strides, views, copies."""

import numpy as np


def main() -> None:
    """Show that an ndarray is a buffer plus a way to read it."""
    a = np.arange(12, dtype=np.int32).reshape(3, 4)
    print(f"a = {a.tolist()}")
    print(f"dtype {a.dtype}, itemsize {a.itemsize}, shape {a.shape}")
    print(f"strides {a.strides} (bytes to the next row, next column)")
    print(f"nbytes {a.nbytes} = size {a.size} * itemsize {a.itemsize}")

    t = a.T
    print(f"a.T is a view: shares_memory {np.shares_memory(a, t)}")
    print(f"a.T strides {t.strides}, C-contiguous {t.flags.c_contiguous}")
    row = a[1]
    col = a[:, 1]
    print(f"a[1] strides {row.strides}, a[:, 1] strides {col.strides}")
    row[0] = 100
    print(f"row[0] = 100 wrote through: a[1, 0] is {a[1, 0]}")

    fancy = a[[0, 2]]
    mask = a[a > 5]
    print(f"a[[0, 2]] shares memory: {np.shares_memory(a, fancy)}")
    print(f"a[a > 5] shares memory: {np.shares_memory(a, mask)}")
    fancy[0, 0] = -1
    print(f"changing the copy leaves a[0, 0] at {a[0, 0]}")
    print(f"a.copy() shares memory: {np.shares_memory(a, a.copy())}")
    print(f"a.ravel() on C order is a view: {np.shares_memory(a, a.ravel())}")
    print(f"t.ravel() has to copy: {not np.shares_memory(t, t.ravel())}")

    small = np.array([100, 200], dtype=np.uint8)
    wrapped = small[1:] + small[:1]
    print(f"uint8 wraps: 200 + 100 -> {wrapped.tolist()}")
    print(f"astype(float32) copies: {small.astype(np.float32).tolist()}")

    # linear algebra: @ is matrix product, norm is the length
    u = np.array([3.0, 4.0])
    m = np.array([[0.0, -1.0], [1.0, 0.0]])
    print(f"norm(u) = {np.linalg.norm(u)}, m @ u = {(m @ u).tolist()}")
    print(f"u @ u = {u @ u} (the dot product), u * u = {(u * u).tolist()}")


if __name__ == "__main__":
    main()
