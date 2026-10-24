"""The manifest: which files were indexed, and under which doc ids.

``.sift/manifest.json`` records, for every Markdown file of the corpus,
its sha256, its mtime and its doc id. Comparing it with the disk tells
``sift index`` what to reparse. Doc ids are stable: a file keeps its id
for life, new files get ``next_doc_id`` onward, and the id of a deleted
file is never used again.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from sift.errors import IndexCorruptError, IndexMissingError
from sift.storage.atomic import atomic_write


@dataclass(frozen=True, slots=True)
class FileEntry:
    """What the index knows about one corpus file."""

    sha256: str
    mtime_ns: int
    doc_id: int


@dataclass(slots=True)
class Manifest:
    """The files of one index; keys of files are corpus-relative paths."""

    corpus: str
    next_doc_id: int = 0
    files: dict[str, FileEntry] = field(default_factory=dict[str, FileEntry])


@dataclass(frozen=True, slots=True)
class Change:
    """A file to (re)parse: its entry once the update is done."""

    relpath: str
    entry: FileEntry


@dataclass(frozen=True, slots=True)
class Plan:
    """What an update must do, and the manifest that results.

    reparse lists the new and the changed files in doc id order;
    removed holds the doc ids of deleted files; unchanged counts the
    files whose entry was kept. Both reparse and removed ids must
    leave the old postings.
    """

    manifest: Manifest
    reparse: list[Change]
    removed: list[int]
    unchanged: int

    @property
    def stale_ids(self) -> set[int]:
        """Return the ids whose old postings must be dropped."""
        return {c.entry.doc_id for c in self.reparse} | set(self.removed)


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of the file at path."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def load_manifest(path: Path) -> Manifest:
    """Read a manifest.

    Raise IndexMissingError if the file does not exist and
    IndexCorruptError if it is not valid JSON of the right shape.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise IndexMissingError(f"no manifest at {path}") from None
    try:
        data = json.loads(text)
        files = {
            relpath: FileEntry(
                str(item["sha256"]), int(item["mtime_ns"]), int(item["doc_id"])
            )
            for relpath, item in data["files"].items()
        }
        return Manifest(str(data["corpus"]), int(data["next_doc_id"]), files)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise IndexCorruptError(f"{path}: bad manifest: {error!r}") from None


def save_manifest(path: Path, manifest: Manifest) -> None:
    """Write the manifest atomically."""
    data = {
        "corpus": manifest.corpus,
        "next_doc_id": manifest.next_doc_id,
        "files": {
            relpath: {
                "sha256": entry.sha256,
                "mtime_ns": entry.mtime_ns,
                "doc_id": entry.doc_id,
            }
            for relpath, entry in sorted(manifest.files.items())
        },
    }
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    atomic_write(path, [text.encode("utf-8")])


def plan_update(corpus: Path, old: Manifest | None) -> Plan:
    """Compare the corpus on disk with the old manifest.

    With old None every file is new, and ids follow sorted path order.
    Otherwise a file is reparsed only when its mtime_ns differs from
    the manifest and its sha256 differs too; a file that was only
    touched keeps its id and gets the new mtime. New files are
    numbered from next_doc_id in sorted path order, and files that
    vanished are listed in removed. The manifest records the resolved
    corpus path.
    """
    paths = sorted(corpus.rglob("*.md"))
    previous = old.files if old else {}
    next_id = old.next_doc_id if old else 0
    files: dict[str, FileEntry] = {}
    reparse: list[Change] = []
    unchanged = 0
    for path in paths:
        relpath = path.relative_to(corpus).as_posix()
        mtime_ns = path.stat().st_mtime_ns
        known = previous.get(relpath)
        if known is not None and known.mtime_ns == mtime_ns:
            files[relpath] = known
            unchanged += 1
            continue
        digest = sha256_file(path)
        if known is None:
            entry = FileEntry(digest, mtime_ns, next_id)
            next_id += 1
            reparse.append(Change(relpath, entry))
        elif known.sha256 == digest:
            entry = FileEntry(digest, mtime_ns, known.doc_id)
            unchanged += 1
        else:
            entry = FileEntry(digest, mtime_ns, known.doc_id)
            reparse.append(Change(relpath, entry))
        files[relpath] = entry
    removed = sorted(
        entry.doc_id for rel, entry in previous.items() if rel not in files
    )
    reparse.sort(key=lambda change: change.entry.doc_id)
    manifest = Manifest(str(corpus.resolve()), next_id, files)
    return Plan(manifest, reparse, removed, unchanged)
