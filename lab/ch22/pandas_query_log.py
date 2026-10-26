"""Read the query log with read_sql after five runs of bench search."""

import os
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from sift.analytics.stats import query_log_frame
from sift.config import load_config
from sift.storage.store import DB, update_index

RUNS = 5


def main() -> None:
    """Build an index, run ``sift bench search`` 5 times, analyze."""
    config = load_config()
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        update_index(config.corpus, directory, config.pipeline)
        env = {**os.environ, "SIFT_INDEX": scratch}
        for _ in range(RUNS):
            subprocess.run(
                ["sift", "bench", "search"],
                env=env,
                check=True,
                capture_output=True,
            )
        log = query_log_frame(directory / DB)
    print(f"{len(log)} rows after {RUNS} runs")
    print(log.dtypes.to_string())
    print(log.head(3).to_string())

    by_query = log.groupby("query")["took_ms"]
    stats = by_query.agg(["count", "median", "min", "max"])
    print("\nlatency per query (ms), slowest median first")
    print(stats.sort_values("median", ascending=False).round(2).to_string())

    # the first run is cold: compare it with the other four
    log["run"] = log.groupby("query").cumcount()
    cold = log["run"] == 0
    print(f"\ncold run median {log.loc[cold, 'took_ms'].median():.2f} ms")
    print(f"warm runs median {log.loc[~cold, 'took_ms'].median():.2f} ms")
    quantiles = log["took_ms"].quantile([0.5, 0.9, 0.99])
    print(pd.DataFrame({"ms": quantiles.round(2)}).to_string())


if __name__ == "__main__":
    main()
