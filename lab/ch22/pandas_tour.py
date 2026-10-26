"""A tour of pandas on the corpus: frames, groupby, resample, CoW."""

import warnings

import pandas as pd

from sift.analysis import build_pipeline
from sift.analytics.stats import corpus_frame
from sift.cli import load_index
from sift.config import load_config


def main() -> None:
    """Walk through the core API with the frame of the corpus."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    frame = corpus_frame(index)
    print(f"shape {frame.shape}")
    print(frame.dtypes.to_string())

    tokens = frame["tokens"]
    print(f"\nSeries: {type(tokens).__name__}, mean {tokens.mean():.1f}")
    print(f"describe:\n{tokens.describe().round(1).to_string()}")

    print("\n.loc by label, .iloc by position")
    print(frame.loc[0, "title"])
    print(frame.iloc[0, 1])
    print(frame.loc[frame["tokens"] > 20_000, ["doc_id", "tokens"]])

    print("\nvalue_counts of category")
    print(frame["category"].value_counts(dropna=False).to_string())

    print("\ngroupby category")
    grouped = frame.groupby("category", dropna=False)["tokens"]
    print(grouped.agg(["count", "mean", "max"]).round(0).to_string())

    series_sizes = frame.groupby("series", dropna=True).size()
    names = series_sizes.rename("posts").reset_index()
    merged = frame.merge(names, on="series", how="left")
    print("\nmerge: posts in the same series")
    print(merged.loc[merged["posts"].notna(), ["title", "posts"]].head(3))

    frame["year"] = frame["published"].dt.strftime("%Y")
    table = frame.pivot_table(
        index="category",
        columns="year",
        values="doc_id",
        aggfunc="count",
        fill_value=0,
    )
    print("\npivot_table: posts by category and year")
    print(table.to_string())

    monthly = frame.set_index("published")["doc_id"].resample("MS").count()
    print(f"\nresample('MS'): {len(monthly)} months")
    print(monthly.sort_values(ascending=False).head(3).to_string())

    copy_on_write(frame)


def copy_on_write(frame: pd.DataFrame) -> None:
    """Show that pandas 3 never changes a frame through a derived one."""
    print("\ncopy-on-write (pandas 3)")
    before = int(frame.loc[0, "tokens"])
    part = frame["tokens"]
    part.iloc[0] = -1
    print(f"part.iloc[0] = -1 -> frame still {frame.loc[0, 'tokens']}")
    assert frame.loc[0, "tokens"] == before

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # chained assignment: the first [] gives a temporary copy
        frame[frame["tokens"] > 0]["tokens"] = 0
    kinds = sorted({w.category.__name__ for w in caught})
    print(f"chained assignment changed nothing: {kinds}")
    assert frame.loc[0, "tokens"] == before

    frame.loc[frame["tokens"] > 0, "flag"] = True
    print(f"one .loc call did write: {int(frame['flag'].sum())} rows")


if __name__ == "__main__":
    main()
