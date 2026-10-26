"""Posts per month: a datetime index and resample("MS")."""

from sift.analysis import build_pipeline
from sift.analytics.stats import corpus_frame, posts_per_month
from sift.cli import load_index
from sift.config import load_config


def main() -> None:
    """Count the posts of each month and print the busiest ones."""
    config = load_config()
    _, index = load_index(config.corpus, build_pipeline(config.pipeline))
    frame = corpus_frame(index)
    print(f"published dtype: {frame['published'].dtype}")
    monthly = posts_per_month(frame)
    print(f"{len(monthly)} months, from {monthly.index[0]:%Y-%m}")
    print(f"empty months: {int((monthly == 0).sum())}")
    peak = monthly.idxmax()
    print(f"peak: {peak:%Y-%m} with {monthly.max()} posts")
    print(monthly.sort_values(ascending=False).head(5).to_string())
    rolling = monthly.rolling(3).sum().dropna()
    print(f"busiest 3 months in a row: {int(rolling.max())} posts")


if __name__ == "__main__":
    main()
