"""``sift report``: the four figures and a Markdown table of numbers."""

from pathlib import Path

from sift.analytics import plots, stats
from sift.analytics.vectors import TermIndex, top_pairs

PAIRS = 5


def write_report(index: TermIndex, db: Path, out: Path) -> list[Path]:
    """Write the figures and ``report.md`` into out; return the paths.

    The figures are ``zipf.png``, ``heaps.png``,
    ``posts-per-month.png`` and ``latency-hist.png``. db is the
    ``sift.db`` that holds the query log (it may have no rows).
    """
    plots.configure_matplotlib()
    out.mkdir(parents=True, exist_ok=True)
    frame = stats.corpus_frame(index)
    log = stats.query_log_frame(db)
    counts = stats.term_counts(index)
    zipf = stats.zipf_fit(counts)
    tokens, vocabulary = stats.vocabulary_growth(index)
    heaps = stats.heaps_fit(tokens, vocabulary)
    monthly = stats.posts_per_month(frame)
    figures = [
        plots.plot_zipf(counts, zipf, out / "zipf.png"),
        plots.plot_heaps(tokens, vocabulary, heaps, out / "heaps.png"),
        plots.plot_posts_per_month(monthly, out / "posts-per-month.png"),
        plots.plot_latency_hist(log["took_ms"], out / "latency-hist.png"),
    ]
    busiest = monthly.idxmax()
    titles = {
        doc_id: title.replace("|", "\\|")
        for doc_id, title in zip(frame["doc_id"], frame["title"], strict=True)
    }
    rows = [
        ("documents", f"{len(frame)}"),
        ("tokens", f"{int(tokens[-1])}"),
        ("distinct terms", f"{int(vocabulary[-1])}"),
        ("Zipf exponent (ranks 1-1000)", f"{zipf.exponent:.3f}"),
        ("Heaps K", f"{heaps.scale:.2f}"),
        ("Heaps beta", f"{heaps.exponent:.3f}"),
        ("busiest month", f"{busiest:%Y-%m} ({monthly.max()} posts)"),
        ("logged queries", f"{len(log)}"),
    ]
    lines = ["# Sift report", "", "| metric | value |", "| --- | --- |"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    lines += ["", "## Most similar posts", ""]
    lines += ["| score | post | post |", "| --- | --- | --- |"]
    for first, second, score in top_pairs(index, PAIRS):
        lines.append(
            f"| {score:.3f} | {titles[first]} ({first}) "
            f"| {titles[second]} ({second}) |"
        )
    lines += ["", "## Figures", ""]
    lines += [f"![{png.stem}]({png.name})" for png in figures]
    report = out / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [*figures, report]
