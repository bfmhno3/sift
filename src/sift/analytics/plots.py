"""The four figures of ``sift report``, drawn with matplotlib's OO API.

Each function builds a ``Figure`` of its own, saves it as a PNG and
returns the path. No pyplot: a ``Figure`` has no global state and
needs no window. The ``Agg`` backend renders to a raster file, and
``configure_matplotlib`` makes the labels print Chinese.
"""

# matplotlib's stubs leave the **kwargs of the Axes methods untyped, and
# strict pyright reports each call as a partially unknown member.
# pyright: reportUnknownMemberType=false

import dataclasses
import logging
import os
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from numpy.typing import NDArray

from sift.analytics.stats import PowerLaw

logger = logging.getLogger(__name__)

FONT_ENV = "SIFT_CJK_FONT"
FIGSIZE = (8.0, 5.0)
DPI = 150
BLUE = "#1f6feb"
ORANGE = "#d1570d"


def configure_matplotlib() -> str | None:
    """Select the Agg backend and a font with CJK glyphs.

    The font file is named by ``SIFT_CJK_FONT``. It is registered
    with ``font_manager.fontManager.addfont`` and set as
    ``rcParams["font.family"]``. Return the family name, or None
    (and log a warning) when the variable is unset or the file is
    missing: the figures then print boxes for Chinese characters.
    """
    matplotlib.use("Agg")
    path = os.environ.get(FONT_ENV)
    if not path or not Path(path).is_file():
        logger.warning("%s is not a font file, CJK text will break", FONT_ENV)
        return None
    font_manager.fontManager.addfont(path)
    family = font_manager.FontProperties(fname=path).get_name()
    # a variable font is listed with the weight of its first named
    # instance (Thin, 100); the lookup for "normal" would then warn
    fonts = font_manager.fontManager.ttflist
    for i, entry in enumerate(fonts):
        if entry.fname == path:
            fonts[i] = dataclasses.replace(entry, weight=400)
    matplotlib.rcParams["font.family"] = family
    return family


def new_figure() -> tuple[Figure, Axes]:
    """Return an empty Figure and its one Axes, laid out to fit."""
    fig = Figure(figsize=FIGSIZE, dpi=DPI, layout="constrained")
    return fig, fig.subplots()


def save(fig: Figure, path: Path) -> Path:
    """Write fig to path as a PNG, creating the directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png")
    return path


def plot_zipf(
    counts: NDArray[np.int64], fit: PowerLaw, path: Path, max_rank: int = 1000
) -> Path:
    """Draw word frequency against rank on log-log axes, with the fit.

    counts is sorted largest first. The line is drawn over the ranks
    that went into the fit.
    """
    fig, ax = new_figure()
    ranks = np.arange(1, len(counts) + 1)
    ax.scatter(ranks, counts, s=4, color=BLUE, label="词项 term")
    fitted = ranks[:max_rank].astype(np.float64)
    ax.plot(
        fitted,
        fit(fitted),
        color=ORANGE,
        linewidth=2,
        label=f"拟合 fit: 频率 ∝ 排名^{fit.exponent:.2f}",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("排名 rank (对数 log)")
    ax.set_ylabel("词频 frequency (对数 log)")
    ax.set_title("齐夫定律：词频与排名")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend()
    return save(fig, path)


def plot_heaps(
    tokens: NDArray[np.int64],
    vocabulary: NDArray[np.int64],
    fit: PowerLaw,
    path: Path,
) -> Path:
    """Draw the vocabulary size against the token count, with the fit."""
    fig, ax = new_figure()
    ax.plot(
        tokens,
        vocabulary,
        color=BLUE,
        linewidth=2,
        label="语料 corpus",
    )
    xs = tokens.astype(np.float64)
    ax.plot(
        xs,
        fit(xs),
        color=ORANGE,
        linestyle="--",
        linewidth=2,
        label=f"拟合 fit: V = {fit.scale:.1f} · n^{fit.exponent:.2f}",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("词元数 tokens n (对数 log)")
    ax.set_ylabel("词汇量 vocabulary V (对数 log)")
    ax.set_title("希普斯定律：词汇量的增长")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend()
    return save(fig, path)


def plot_posts_per_month(counts: pd.Series[int], path: Path) -> Path:
    """Draw a bar for each month, and mark the busiest one."""
    fig, ax = new_figure()
    months = [stamp.strftime("%Y-%m") for stamp in counts.index]
    values = counts.to_numpy()
    where = np.arange(len(values))
    ax.bar(where, values, width=0.8, color=BLUE)
    peak = int(np.argmax(values))
    ax.annotate(
        f"{months[peak]}: {values[peak]} 篇",
        xy=(where[peak], values[peak]),
        xytext=(-40, -4),
        textcoords="offset points",
        ha="right",
        arrowprops={"arrowstyle": "->", "color": ORANGE},
        color=ORANGE,
    )
    step = -(-len(months) // 12)
    ticks = where[::step]
    ax.set_xticks(ticks, [months[i] for i in ticks], rotation=45)
    ax.set_xlabel("月份 month")
    ax.set_ylabel("文章数 posts")
    ax.set_title("每月发布的文章数")
    ax.grid(True, axis="y", alpha=0.3)
    return save(fig, path)


def plot_latency_hist(took_ms: pd.Series[float], path: Path) -> Path:
    """Draw the histogram of the logged query times on a log x axis.

    The bins are equal in log space, so a fast query and a slow one
    each get a readable bar. With an empty log the figure says so.
    """
    fig, ax = new_figure()
    ax.set_xlabel("耗时 latency (毫秒 ms, 对数 log)")
    ax.set_ylabel("查询数 queries")
    ax.set_title("查询耗时分布")
    values = took_ms.to_numpy(dtype=np.float64)
    values = values[values > 0]
    if values.size == 0:
        ax.text(
            0.5,
            0.5,
            "还没有记录的查询 (先运行 sift bench search)",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return save(fig, path)
    low, high = float(values.min()), float(values.max())
    edges: list[float] = np.geomspace(low, high * 1.000001, 21).tolist()
    ax.hist(
        values,
        bins=edges,
        color=BLUE,
        edgecolor="white",
    )
    median = float(np.median(values))
    ax.axvline(
        median, color=ORANGE, linewidth=2, label=f"中位数 {median:.1f} ms"
    )
    ax.set_xscale("log")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    return save(fig, path)
