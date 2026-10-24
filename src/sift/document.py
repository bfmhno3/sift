"""The Document value type: one parsed post."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo

from sift.errors import FrontMatterError
from sift.frontmatter import Value, parse_front_matter
from sift.markdown import split_front_matter, strip_markdown

SHANGHAI = ZoneInfo("Asia/Shanghai")
_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M %z")


def parse_datetime(value: str) -> datetime:
    """Return value as an aware datetime in Asia/Shanghai.

    Accepts ``"YYYY-MM-DD HH:MM:SS +08:00"``, the same without the
    seconds, and a bare ``YYYY-MM-DD`` (midnight in Asia/Shanghai).
    Other formats raise ValueError.
    """
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt).astimezone(SHANGHAI)
        except ValueError:
            continue
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=SHANGHAI)
    except ValueError:
        raise ValueError(f"unrecognized date: {value!r}") from None


def _key_line(front: str, key: str) -> int:
    """Return the line in the file of ``key:`` in the front matter.

    Line 1 is the opening ``---``, so the front matter starts at
    line 2. A missing key is reported on line 1.
    """
    for number, line in enumerate(front.splitlines(), 2):
        if line.startswith(f"{key}:"):
            return number
    return 1


def _date(value: str, front: str, key: str, path: Path) -> datetime:
    """Parse the date in meta[key], or raise a FrontMatterError."""
    try:
        return parse_datetime(value)
    except ValueError as exc:
        raise FrontMatterError(path, _key_line(front, key), str(exc)) from None


def _optional_str(meta: dict[str, Value], key: str) -> str | None:
    """Return meta[key] as str, or None when the key is absent."""
    return None if key not in meta else str(meta[key])


@dataclass(frozen=True, slots=True)
class Document:
    """A post: its metadata and its text with Markdown stripped."""

    doc_id: int
    path: Path
    title: str
    published: datetime
    updated: datetime | None
    tags: tuple[str, ...]
    category: str | None
    series: str | None
    body: str

    @classmethod
    def from_markdown(cls, doc_id: int, path: Path, text: str) -> Self:
        """Build a Document from the raw text of a Markdown file.

        Raises FrontMatterError if the front matter is malformed or
        lacks a title or a publication date, or a date is unreadable.
        """
        front, body = split_front_matter(text)
        meta = parse_front_matter(front, path, first_line=2)
        for key in ("title", "published"):
            if key not in meta:
                raise FrontMatterError(path, 1, f"missing {key!r}")
        updated = _optional_str(meta, "updated")
        raw_tags = meta.get("tags", [])
        tags = raw_tags if isinstance(raw_tags, list) else [raw_tags]
        return cls(
            doc_id=doc_id,
            path=path,
            title=str(meta["title"]),
            published=_date(str(meta["published"]), front, "published", path),
            updated=(
                None
                if updated is None
                else _date(updated, front, "updated", path)
            ),
            tags=tuple(map(str, tags)),
            category=_optional_str(meta, "category"),
            series=_optional_str(meta, "series"),
            body=strip_markdown(body),
        )
