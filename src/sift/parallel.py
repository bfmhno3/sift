"""Parallel indexing: parse and analyze files on several workers.

The contract
------------

``index_items(items, pipeline_names, jobs=..., mode=...)`` returns the
InvertedIndex of the items. For the same items and pipeline it returns
an index equal to the serial one (jobs=1), with the same doc_ids,
the same postings and the same term order, whatever jobs and mode are.
The segment file written from it is byte for byte the same.

Work is split into contiguous chunks of items, at most ``jobs *
CHUNKS_PER_JOB`` of them. A worker parses and analyzes one chunk and
sends back a small InvertedIndex (a ``Part``); the caller merges the
parts in chunk order. Nothing depends on which worker finishes first.

Modes (``MODES``):

``process``
    ProcessPoolExecutor. Own interpreter and GIL per worker, arguments
    and results pickled through a pipe.
``thread``
    ThreadPoolExecutor. One interpreter, one address space: no copy,
    but the GIL lets one thread run Python code at a time, so it only
    scales on a free-threaded build.
``interp``
    InterpreterPoolExecutor (PEP 734). Threads, each running its own
    subinterpreter with its own GIL; data is pickled as in ``process``.

jobs=1 runs in the calling thread with no pool, whatever the mode.
A jobs below 1 or a mode outside MODES raises ValueError.

Errors:

- A file that cannot be parsed or read does not stop its chunk. After
  the last chunk one ``ExceptionGroup("N files failed", ...)`` is
  raised, in item order, holding FrontMatterError for bad front
  matter and SiftError for a file that cannot be read.
- Any other exception in a worker is re-raised in the caller as it
  is. The chunks not yet started are cancelled.
- A worker that dies (``BrokenExecutor``) raises SiftError.

Workers only import modules that do not need SQLAlchemy, and the
functions they run live at module level, so every mode can find them
by name.

The cyclic garbage collector is paused while a chunk is analyzed and
while the parts are merged (``gc_paused``): see its docstring.

``bench_index`` times ``index_items`` for a grid of jobs and modes on
a corpus copied in memory; ``sift bench index`` prints its result.
"""

import gc
import sys
from collections.abc import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    Sequence,
)
from concurrent.futures import (
    BrokenExecutor,
    Executor,
    InterpreterPoolExecutor,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
)
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Literal, get_args

from sift.analysis import build_pipeline
from sift.document import Document
from sift.errors import FrontMatterError, SiftError
from sift.index import IndexWriter, InvertedIndex

Mode = Literal["process", "thread", "interp"]
MODES: tuple[Mode, ...] = get_args(Mode)
CHUNKS_PER_JOB = 4


@dataclass(frozen=True, slots=True)
class Item:
    """One document to index: its id, its file and maybe its text.

    With text None the worker reads path as UTF-8; otherwise it
    parses text and uses path only to name the file in errors.
    """

    doc_id: int
    path: str
    text: str | None = None


@dataclass(frozen=True, slots=True)
class Part:
    """What a worker sends back for one chunk."""

    index: InvertedIndex
    errors: tuple[SiftError, ...]


def gil_enabled() -> bool:
    """Return True if the GIL is on in this interpreter.

    A standard build always has it; a free-threaded build (python3.14t)
    runs without it unless PYTHON_GIL=1 or an extension module turned
    it back on. sys._is_gil_enabled is private and absent before 3.13.
    """
    probe = getattr(sys, "_is_gil_enabled", None)
    return bool(probe()) if callable(probe) else True


def check_jobs(jobs: int, mode: str) -> None:
    """Raise ValueError unless jobs is at least 1 and mode is known."""
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, not {jobs}")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}, use one of {MODES}")


def make_executor(mode: Mode, workers: int) -> Executor:
    """Return a pool of workers workers for mode."""
    match mode:
        case "process":
            return ProcessPoolExecutor(workers)
        case "thread":
            return ThreadPoolExecutor(workers)
        case "interp":
            return InterpreterPoolExecutor(workers)


def run_ordered[T, R](
    func: Callable[[T], R],
    items: Sequence[T],
    *,
    jobs: int,
    mode: Mode,
) -> Iterator[R]:
    """Yield func(item) for each item, in item order.

    With jobs=1, or fewer than two items, func runs in the calling
    thread and no pool is made. Otherwise a pool of min(jobs,
    len(items)) workers runs it. An exception of func is raised
    where the result of that item would be yielded; the items not
    started yet are cancelled and the pool is shut down before the
    exception leaves. func and the items must be picklable in modes
    process and interp, and func must be a function that can be
    found by its module and name.
    """
    check_jobs(jobs, mode)
    return _run_ordered(func, items, min(jobs, len(items)), mode)


def _run_ordered[T, R](
    func: Callable[[T], R], items: Sequence[T], workers: int, mode: Mode
) -> Iterator[R]:
    """Yield the results of run_ordered, on workers workers."""
    if workers <= 1:
        yield from map(func, items)
        return
    pool = make_executor(mode, workers)
    try:
        yield from pool.map(func, items)
    except BrokenExecutor as error:
        raise SiftError(f"a worker died: {error}") from error
    finally:
        pool.shutdown(cancel_futures=True)


@contextmanager
def gc_paused() -> Generator[None]:
    """Switch the cyclic garbage collector off inside the block.

    Indexing builds millions of tuples and Posting objects that live
    until the end and form no cycles. Each young collection walks
    them in vain: pausing the collector makes the analysis a quarter
    faster and unpickling a worker result four times faster. The
    state before the block comes back after it. The switch belongs to
    the interpreter, so nested uses and worker threads are safe: only
    the block that found the collector on turns it on again.
    """
    was_on = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_on:
            gc.enable()


def index_chunk(items: tuple[Item, ...], names: tuple[str, ...]) -> Part:
    """Parse and analyze items; the unit of work of a worker."""
    with gc_paused():
        return _index_chunk(items, names)


def _index_chunk(items: tuple[Item, ...], names: tuple[str, ...]) -> Part:
    """Return the Part of items, with the collector already paused."""
    index = InvertedIndex()
    errors: list[SiftError] = []
    with IndexWriter(index, build_pipeline(names)) as writer:
        for item in items:
            path = Path(item.path)
            try:
                text = item.text
                if text is None:
                    text = path.read_text(encoding="utf-8")
                doc = Document.from_markdown(item.doc_id, path, text)
            except FrontMatterError as error:
                errors.append(error)
            except (OSError, UnicodeDecodeError) as error:
                errors.append(SiftError(f"cannot read {path}: {error}"))
            else:
                writer.add(doc)
    return Part(index, tuple(errors))


def split(items: Sequence[Item], parts: int) -> list[tuple[Item, ...]]:
    """Cut items into at most parts contiguous, near-equal chunks.

    Chunk sizes differ by at most one, longer chunks first. There are
    no empty chunks, except the single one of an empty items.
    """
    parts = max(1, min(parts, len(items)))
    size, extra = divmod(len(items), parts)
    chunks: list[tuple[Item, ...]] = []
    start = 0
    for i in range(parts):
        stop = start + size + (i < extra)
        chunks.append(tuple(items[start:stop]))
        start = stop
    return chunks


def index_items(
    items: Iterable[Item],
    pipeline_names: Sequence[str],
    *,
    jobs: int = 1,
    mode: Mode = "process",
) -> InvertedIndex:
    """Return the index of items, built by jobs workers of mode.

    The items must come in increasing doc_id order. See the module
    docstring for the guarantees and the errors.
    """
    check_jobs(jobs, mode)
    ordered = list(items)
    names = tuple(pipeline_names)
    chunks = split(ordered, jobs * CHUNKS_PER_JOB if jobs > 1 else 1)
    merged: InvertedIndex | None = None
    errors: list[SiftError] = []
    with gc_paused():
        for part in run_ordered(
            partial(index_chunk, names=names), chunks, jobs=jobs, mode=mode
        ):
            errors.extend(part.errors)
            if errors:
                continue
            if merged is None:
                merged = part.index
            else:
                merged.merge(part.index)
    if errors:
        noun = "file" if len(errors) == 1 else "files"
        raise ExceptionGroup(f"{len(errors)} {noun} failed", errors)
    return merged if merged is not None else InvertedIndex()


def read_items(root: Path) -> list[Item]:
    """Return one Item per ``*.md`` file under root, text included.

    Files come in sorted path order and the doc_id of an item is its
    position, as in iter_documents.
    """
    return [
        Item(doc_id, str(path), path.read_text(encoding="utf-8"))
        for doc_id, path in enumerate(sorted(root.rglob("*.md")))
    ]


def replicate(items: Sequence[Item], repeat: int) -> list[Item]:
    """Return items repeated repeat times with doc_ids renumbered.

    Copy k of the item at position i gets the doc_id ``k * len(items)
    + i``, so the result is a larger corpus with unique, increasing
    doc_ids. The texts are shared, not copied.
    """
    if repeat < 1:
        raise ValueError(f"repeat must be at least 1, not {repeat}")
    return [
        Item(copy * len(items) + i, item.path, item.text)
        for copy in range(repeat)
        for i, item in enumerate(items)
    ]


def fingerprint(index: InvertedIndex) -> tuple[int, int, int]:
    """Return (documents, terms, tokens): a cheap check of an index."""
    tokens = sum(index.doc_len(doc_id) for doc_id in index.documents)
    return index.n_docs, len(index), tokens


@dataclass(frozen=True, slots=True)
class Timing:
    """The best time of one (jobs, mode) cell of the benchmark."""

    jobs: int
    mode: Mode
    seconds: float


def bench_index(
    items: Sequence[Item],
    pipeline_names: Sequence[str],
    jobs: Sequence[int],
    modes: Sequence[Mode],
    *,
    rounds: int = 3,
) -> tuple[float, list[Timing]]:
    """Time index_items for every jobs and mode; return the serial time.

    Returns (serial seconds, timings), the timings in jobs-major order
    like the arguments. The serial build (jobs=1, no pool) is timed
    once and stands for the cell jobs=1 of every mode. Every cell is
    run rounds times, interleaved so that a slow phase of the machine
    hits all cells, and the best time is kept. The time covers
    everything index_items does, pool start-up included. A cell
    whose index differs from the serial one raises SiftError.
    """
    if rounds < 1:
        raise ValueError(f"rounds must be at least 1, not {rounds}")
    for count in jobs:
        check_jobs(count, "process")
    cells: list[tuple[int, Mode]] = [
        (n, m) for n in jobs if n > 1 for m in modes
    ]
    best: dict[tuple[int, Mode], float] = {}
    serial = float("inf")
    expected: tuple[int, int, int] | None = None
    for _ in range(rounds):
        start = perf_counter()
        base = index_items(items, pipeline_names)
        serial = min(serial, perf_counter() - start)
        expected = fingerprint(base)
        for n, mode in cells:
            start = perf_counter()
            built = index_items(items, pipeline_names, jobs=n, mode=mode)
            took = perf_counter() - start
            if fingerprint(built) != expected:
                raise SiftError(f"jobs={n} mode={mode} built another index")
            best[n, mode] = min(best.get((n, mode), took), took)
    return serial, [
        Timing(n, m, serial if n == 1 else best[n, m])
        for n in jobs
        for m in modes
    ]
