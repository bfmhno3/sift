# sift

Companion code for the blog series "用 Sift 重学 Python". Sift is a local full-text search engine over the Markdown
posts of <https://bfmhno3.github.io>: inverted index, BM25, a hand-written query language, a CLI, binary index files,
SQLite, parallel indexing, asyncio and FastAPI servers, tkinter and PySide6 clients, data analysis, profiling, and C and
Rust extensions. Everything runs on Python 3.14.7. Each chapter is a git tag (`ch01` ... `ch25`); `git checkout chNN`
gives the state of the repository when post NN was written.

## Chapters

| Chapter | Topic | Post |
| --- | --- | --- |
| `ch01` | Interpreter, objects, the first naive search | `/posts/python-by-sift-01-first-search/` |
| `ch02` | `str`, `bytes`, Unicode, regular expressions | `/posts/python-by-sift-02-text-and-unicode/` |
| `ch03` | `list`, `dict`, `set`, `collections` | `/posts/python-by-sift-03-containers/` |
| `ch04` | Functions, closures, decorators, `functools` | `/posts/python-by-sift-04-functions/` |
| `ch05` | Iterators, generators, `itertools` | `/posts/python-by-sift-05-iterators-generators/` |
| `ch06` | Classes, the data model, dataclasses | `/posts/python-by-sift-06-classes-data-model/` |
| `ch07` | Inheritance, ABC, Protocol, analyzer plugins | `/posts/python-by-sift-07-inheritance-protocols/` |
| `ch08` | BM25, the query language, `match`/`case` | `/posts/python-by-sift-08-bm25-query-language/` |
| `ch09` | Exceptions, context managers, logging, pdb | `/posts/python-by-sift-09-exceptions-context-logging/` |
| `ch10` | pytest, hypothesis, CI | `/posts/python-by-sift-10-testing/` |
| `ch11` | Modules, packages, imports, argparse | `/posts/python-by-sift-11-modules-packaging-cli/` |
| `ch12` | Files, `struct`, varint, `mmap`, compression | `/posts/python-by-sift-12-files-binary-format/` |
| `ch13` | `sqlite3`, FTS5, SQLAlchemy | `/posts/python-by-sift-13-sqlite-sqlalchemy/` |
| `ch14` | Type annotations, mypy, pyright | `/posts/python-by-sift-14-type-system/` |
| `ch15` | Descriptors, metaclasses, bytecode, GC | `/posts/python-by-sift-15-metaprogramming/` |
| `ch16` | Threads, processes, the GIL, free threading | `/posts/python-by-sift-16-threads-processes-gil/` |
| `ch17` | asyncio and a hand-written HTTP server | `/posts/python-by-sift-17-asyncio/` |
| `ch18` | FastAPI, pydantic, httpx | `/posts/python-by-sift-18-fastapi-pydantic-httpx/` |
| `ch19` | typer, rich, uv, wheels | `/posts/python-by-sift-19-typer-rich-uv/` |
| `ch20` | tkinter | `/posts/python-by-sift-20-tkinter/` |
| `ch21` | PySide6 desktop client | `/posts/python-by-sift-21-pyside6/` |
| `ch22` | numpy, pandas, matplotlib | `/posts/python-by-sift-22-numpy-pandas-matplotlib/` |
| `ch23` | Profiling and optimization | `/posts/python-by-sift-23-profiling-performance/` |
| `ch24` | C extensions: ctypes, cffi, Cython, C API | `/posts/python-by-sift-24-c-extensions/` |
| `ch25` | Rust extension with PyO3 | `/posts/python-by-sift-25-pyo3-rust/` |

The posts live at <https://bfmhno3.github.io>.

## Layout

```text
pyproject.toml       package metadata (hatchling), pytest settings, the `sift` script
sift.toml            settings: corpus, index directory, analysis pipeline, BM25
src/sift/            the package (parallel.py: process, thread and interpreter pools)
tests/               pytest suite and the tiny fixture corpus in tests/fixtures/mini
.github/workflows/   CI: `nix develop --command make corpus ci`
lab/chNN/            one directory of small lab files per chapter
bench/queries.txt    the queries used by every benchmark
scripts/             chapter runner and corpus fetcher
corpus/              the blog posts, fetched by `make corpus` (not committed)
.sift/               the index written by `sift index` (not committed)
out/                 outputs of the lab files (not committed)
```

Lab file conventions, enforced by `scripts/chapter.py`:

- Every top-level `lab/chNN/*.py` runs with `python3`; stdout and stderr go to `out/chNN/<name>.stdout` and `.stderr`.
- `*_fail.py` and `*_syntaxerror.py` must exit non-zero, everything else must exit 0.
- `*_ft.py` runs with `python3.14t` (free-threaded), `*_gui.py` runs under Xvfb.
- `lab/chNN/extra.sh`, if present, runs afterwards for chapter-specific commands.

## Running

Everything runs from the repository root inside the Nix dev shell. The first `nix develop` creates `.venv` (with
`--system-site-packages`) and installs Sift into it in editable mode, so `sift` and `python3 -m sift` work.

```bash
nix develop
make corpus    # fetch the 123 posts into corpus/ (pinned commit)
make ch01      # one chapter
make typecheck # mypy --strict and pyright strict on src/
make test      # the pytest suite (python3 -m pytest) (make cov adds coverage)
make ci        # lint, typecheck, tests and every chapter
sift index     # writes .sift/ (segment.sft, sift.db, manifest.json)
sift search --limit 3 rust
sift index --full --jobs 4 --mode thread   # modes: process, thread, interp
sift bench index --repeat 8 --jobs 1,2,4,8 --mode process,thread,interp
PYTHONPATH=src python3.14t -m sift bench index --mode thread   # free-threaded, no venv
```

## Corpus license

The posts are licensed CC BY-NC-SA 4.0, so they are fetched from the blog repository at a pinned commit and never
redistributed here.

## License

Dual licensed under MIT or Apache-2.0, see `LICENSE-MIT` and `LICENSE-APACHE`.
