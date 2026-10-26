"""matplotlib's Figure/Axes API against the pyplot state machine."""

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402


def with_pyplot(path: Path, xs: np.ndarray) -> None:
    """Draw with the global state: plt.plot acts on the current Axes."""
    plt.figure(figsize=(4, 3))
    plt.plot(xs, xs**2, label="x^2")
    plt.xscale("log")
    plt.yscale("log")
    plt.title("pyplot")
    plt.legend()
    plt.savefig(path)
    plt.close()


def with_objects(path: Path, xs: np.ndarray) -> None:
    """Draw with objects: no global state, no pyplot import needed."""
    fig = Figure(figsize=(4, 3), layout="constrained")
    ax = fig.subplots()
    ax.plot(xs, xs**2, label="x^2")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("Figure and Axes")
    ax.legend()
    fig.savefig(path)


def main() -> None:
    """Draw the same curve both ways and compare the state left over."""
    xs = np.logspace(0, 3, 50)
    print(f"backend: {matplotlib.get_backend()}")
    with tempfile.TemporaryDirectory() as scratch:
        first, second = Path(scratch, "a.png"), Path(scratch, "b.png")
        with_pyplot(first, xs)
        print(f"open pyplot figures after plt.close(): {plt.get_fignums()}")
        plt.figure()
        print(f"plt.figure() without close: {plt.get_fignums()}")
        plt.close("all")
        with_objects(second, xs)
        print(f"open pyplot figures after Figure(): {plt.get_fignums()}")
        print(f"PNG sizes: {first.stat().st_size}, {second.stat().st_size}")
    ax = Figure().subplots()
    print(f"Axes belongs to {type(ax.figure).__name__}, not to pyplot")
    print(f"rcParams font.family: {matplotlib.rcParams['font.family']}")


if __name__ == "__main__":
    main()
