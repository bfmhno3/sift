"""Tests for sift.parallel: same index in every mode, errors, bench."""

import os
import threading
from pathlib import Path

import pytest

from sift.analysis import build_pipeline
from sift.corpus import iter_documents
from sift.document import Document
from sift.errors import FrontMatterError, SiftError
from sift.index import IndexWriter, InvertedIndex
from sift.parallel import (
    MODES,
    Item,
    Mode,
    bench_index,
    check_jobs,
    fingerprint,
    gil_enabled,
    index_items,
    read_items,
    replicate,
    run_ordered,
    split,
)

NAMES = ("mixed", "nfkc", "stopwords")
GOOD = '---\ntitle: T{n}\npublished: "2026-01-0{n} 08:00:00 +08:00"\n---\nx'
BAD = "---\ntitle: [oops\n---\nx\n"


def serial_index(root: Path) -> InvertedIndex:
    """Build the index with the plain loop of ch09, no parallel code."""
    index = InvertedIndex()
    with IndexWriter(index, build_pipeline(NAMES)) as writer:
        for doc in iter_documents(root):
            writer.add(doc)
    return index


def same_index(a: InvertedIndex, b: InvertedIndex) -> bool:
    """Compare two indexes down to term order and the title index."""
    return (
        list(a) == list(b)
        and a == b
        and list(a.title_index) == list(b.title_index)
        and a.title_index == b.title_index
        and a.documents == b.documents
        and all(a.doc_len(i) == b.doc_len(i) for i in a.documents)
    )


def items_of(texts: dict[str, str], root: Path) -> list[Item]:
    """Write texts under root; return path-only items in name order."""
    for name, text in texts.items():
        (root / name).write_text(text, encoding="utf-8")
    return [
        Item(i, str(path)) for i, path in enumerate(sorted(root.glob("*.md")))
    ]


def test_split_is_contiguous_balanced_and_never_empty() -> None:
    items = [Item(i, f"{i}.md") for i in range(10)]
    chunks = split(items, 4)
    assert [len(c) for c in chunks] == [3, 3, 2, 2]
    assert [item for c in chunks for item in c] == items
    assert len(split(items, 99)) == 10
    assert len(split(items, 0)) == 1
    assert split([], 3) == [()]


def test_check_jobs() -> None:
    check_jobs(1, "process")
    for bad in (0, -3):
        with pytest.raises(ValueError, match="jobs must be at least 1"):
            check_jobs(bad, "thread")
    with pytest.raises(ValueError, match="unknown mode 'fork'"):
        check_jobs(2, "fork")


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("jobs", [1, 2, 5])
def test_index_equals_the_serial_loop(
    mini_root: Path, mode: Mode, jobs: int
) -> None:
    built = index_items(read_items(mini_root), NAMES, jobs=jobs, mode=mode)
    assert same_index(built, serial_index(mini_root))


def test_index_does_not_depend_on_item_text_being_inline(
    mini_root: Path,
) -> None:
    inline = read_items(mini_root)
    by_path = [Item(i.doc_id, i.path) for i in inline]
    a = index_items(inline, NAMES)
    b = index_items(by_path, NAMES, jobs=3, mode="thread")
    assert same_index(a, b)


def test_chunking_does_not_change_the_term_order(mini_root: Path) -> None:
    items = read_items(mini_root)
    orders = {
        tuple(index_items(items, NAMES, jobs=j, mode="thread"))
        for j in (1, 2, 3, 8)
    }
    assert len(orders) == 1


def test_no_items_gives_an_empty_index() -> None:
    for jobs in (1, 3):
        built = index_items([], NAMES, jobs=jobs, mode="thread")
        assert fingerprint(built) == (0, 0, 0)


@pytest.mark.parametrize("mode", MODES)
def test_bad_front_matter_is_one_group_in_item_order(
    tmp_path: Path, mode: Mode
) -> None:
    items = items_of(
        {
            "a.md": GOOD.format(n=1),
            "b.md": BAD,
            "c.md": GOOD.format(n=3),
            "d.md": BAD,
            "e.md": GOOD.format(n=5),
        },
        tmp_path,
    )
    with pytest.raises(ExceptionGroup) as caught:
        index_items(items, NAMES, jobs=3, mode=mode)
    assert caught.value.message == "2 files failed"
    errors = caught.value.exceptions
    assert all(isinstance(e, FrontMatterError) for e in errors)
    assert [Path(str(e.path)).name for e in errors] == [
        "b.md",
        "d.md",
    ]


@pytest.mark.parametrize("mode", MODES)
def test_unreadable_files_are_sift_errors(tmp_path: Path, mode: Mode) -> None:
    items = items_of(
        {"a.md": GOOD.format(n=1), "b.md": GOOD.format(n=2)}, tmp_path
    )
    (tmp_path / "b.md").write_bytes(b"---\ntitle: \xff\xfe\n---\n")
    items.append(Item(2, str(tmp_path / "gone.md")))
    with pytest.raises(ExceptionGroup) as caught:
        index_items(items, NAMES, jobs=2, mode=mode)
    assert caught.value.message == "2 files failed"
    messages = [str(e) for e in caught.value.exceptions]
    assert all(m.startswith("cannot read ") for m in messages)
    assert "b.md" in messages[0] and "gone.md" in messages[1]


def test_a_failed_chunk_leaves_nothing_half_merged(tmp_path: Path) -> None:
    texts = {f"{c}.md": GOOD.format(n=i) for i, c in enumerate("abcd", 1)}
    texts["c.md"] = BAD
    items = items_of(texts, tmp_path)
    with pytest.raises(ExceptionGroup):
        index_items(items, NAMES, jobs=2, mode="thread")


@pytest.mark.parametrize("mode", MODES)
def test_run_ordered_keeps_item_order(mode: Mode) -> None:
    texts = [str(n) for n in range(20)]
    assert list(run_ordered(int, texts, jobs=4, mode=mode)) == list(range(20))


@pytest.mark.parametrize("mode", MODES)
def test_run_ordered_raises_the_error_of_the_worker(mode: Mode) -> None:
    results = run_ordered(int, ["1", "2", "x", "4"], jobs=2, mode=mode)
    assert next(results) == 1
    assert next(results) == 2
    with pytest.raises(ValueError, match="invalid literal"):
        next(results)


def test_run_ordered_with_one_job_runs_in_this_thread() -> None:
    def ident(_: int) -> int:
        return threading.get_ident()

    idents = list(run_ordered(ident, [0, 1], jobs=1, mode="process"))
    assert idents == [threading.get_ident()] * 2
    with pytest.raises(ValueError, match="invalid literal"):
        list(run_ordered(int, ["x"], jobs=1, mode="process"))


def test_run_ordered_checks_jobs_before_the_first_result() -> None:
    with pytest.raises(ValueError, match="jobs must be at least 1"):
        run_ordered(int, ["1"], jobs=0, mode="thread")
    with pytest.raises(ValueError, match="unknown mode"):
        run_ordered(int, ["1"], jobs=2, mode="fork")  # type: ignore[arg-type]


def test_a_dead_worker_is_a_sift_error() -> None:
    with pytest.raises(SiftError, match="a worker died"):
        list(run_ordered(os._exit, [3, 3], jobs=2, mode="process"))


def test_index_items_checks_jobs_and_mode(mini_root: Path) -> None:
    items = read_items(mini_root)
    with pytest.raises(ValueError, match="jobs must be at least 1"):
        index_items(items, NAMES, jobs=0)
    with pytest.raises(ValueError, match="unknown mode"):
        index_items(items, NAMES, jobs=2, mode="fork")  # type: ignore[arg-type]


def test_read_items_and_replicate(mini_root: Path) -> None:
    base = read_items(mini_root)
    assert [i.doc_id for i in base] == list(range(8))
    assert all(i.text for i in base)
    copies = replicate(base, 3)
    assert [i.doc_id for i in copies] == list(range(24))
    assert [i.path for i in copies[8:16]] == [i.path for i in base]
    assert copies[9].text is base[1].text
    with pytest.raises(ValueError, match="repeat must be at least 1"):
        replicate(base, 0)


def test_replicated_corpus_indexes_like_n_documents(mini_root: Path) -> None:
    items = replicate(read_items(mini_root), 3)
    built = index_items(items, NAMES, jobs=2, mode="thread")
    one = index_items(read_items(mini_root), NAMES)
    n_docs, terms, tokens = fingerprint(one)
    assert fingerprint(built) == (3 * n_docs, terms, 3 * tokens)
    docs: list[Document] = list(built.documents.values())
    assert [d.doc_id for d in docs] == list(range(24))


def test_bench_index_returns_one_timing_per_cell(mini_root: Path) -> None:
    items = replicate(read_items(mini_root), 2)
    serial, timings = bench_index(
        items, NAMES, [1, 2], ["thread", "process"], rounds=1
    )
    assert [(t.jobs, t.mode) for t in timings] == [
        (1, "thread"),
        (1, "process"),
        (2, "thread"),
        (2, "process"),
    ]
    assert timings[0].seconds == timings[1].seconds == serial > 0
    assert all(t.seconds > 0 for t in timings)


def test_bench_index_validates_its_arguments(mini_root: Path) -> None:
    items = read_items(mini_root)
    with pytest.raises(ValueError, match="jobs must be at least 1"):
        bench_index(items, NAMES, [0], ["thread"])
    with pytest.raises(ValueError, match="rounds must be at least 1"):
        bench_index(items, NAMES, [1], ["thread"], rounds=0)


def test_gil_enabled_is_a_bool() -> None:
    assert isinstance(gil_enabled(), bool)
