"""datetime and zoneinfo: aware vs naive, timedelta, corpus dates."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sift.document import SHANGHAI, parse_datetime
from sift.frontmatter import parse_front_matter
from sift.markdown import split_front_matter

ROOT = Path("corpus/posts")


def main() -> None:
    """Parse the dates of the corpus and compare datetimes."""
    print("tz:", SHANGHAI, "key:", SHANGHAI.key)
    for text in [
        "2026-04-05 16:20:00 +08:00",
        "2025-10-18 22:30 +08:00",
        "2026-09-01",
    ]:
        dt = parse_datetime(text)
        print(f"{text!r:32} -> {dt.isoformat()} {dt.tzname()}")

    naive = datetime(2026, 1, 1, 8, 0)
    aware = datetime(2026, 1, 1, 8, 0, tzinfo=SHANGHAI)
    print(
        "naive.tzinfo:", naive.tzinfo, "aware.utcoffset():", aware.utcoffset()
    )
    print("aware in UTC:", aware.astimezone(UTC).isoformat())
    print(
        "same instant in New York:",
        aware.astimezone(ZoneInfo("America/New_York")).isoformat(),
    )
    print("naive == aware:", naive == aware)
    try:
        print(naive < aware)
    except TypeError as exc:
        # error: TypeError: can't compare offset-naive and offset-aware
        # datetimes
        print("naive < aware ->", exc)
    try:
        print(aware - naive)
    except TypeError as exc:
        print("aware - naive ->", exc)

    delta = aware - datetime(2025, 12, 25, 8, 0, tzinfo=UTC)
    print("timedelta:", delta, "days:", delta.days, "seconds:", delta.seconds)
    print("aware + 36h:", (aware + timedelta(hours=36)).isoformat())

    dates = []
    for path in sorted(ROOT.glob("*.md")):
        meta = parse_front_matter(
            split_front_matter(path.read_text(encoding="utf-8"))[0]
        )
        dates.append((parse_datetime(str(meta["published"])), path.name))
    dates.sort()
    print("posts:", len(dates))
    print("oldest:", dates[0][0].date(), dates[0][1])
    print("newest:", dates[-1][0].date(), dates[-1][1])
    print("span:", dates[-1][0] - dates[0][0])


if __name__ == "__main__":
    main()
