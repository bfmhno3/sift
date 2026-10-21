"""The Document value type: one parsed post."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo

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

        Raises ValueError if the front matter is malformed or lacks a
        title or a publication date.
        """
        front, body = split_front_matter(text)
        try:
            meta = parse_front_matter(front)
            title = str(meta["title"])
            published = parse_datetime(str(meta["published"]))
            updated = _optional_str(meta, "updated")
            tags = meta.get("tags", [])
            if not isinstance(tags, list):
                tags = [tags]
            return cls(
                doc_id=doc_id,
                path=path,
                title=title,
                published=published,
                updated=None if updated is None else parse_datetime(updated),
                tags=tuple(map(str, tags)),
                category=_optional_str(meta, "category"),
                series=_optional_str(meta, "series"),
                body=strip_markdown(body),
            )
        except KeyError as exc:
            raise ValueError(f"{path}: missing {exc}") from None
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
