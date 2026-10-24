"""weakref: ref, finalize, WeakValueDictionary, and Searcher's cache."""

import gc
import weakref
from dataclasses import replace

from sift.analysis import build_pipeline
from sift.cli import CORPUS, QUERIES, load_index
from sift.document import Document
from sift.search import Searcher


class Blob:
    """Something big enough to want to cache."""

    def __init__(self, name: str) -> None:
        self.name = name


class Slotted:
    __slots__ = ("x",)


def main() -> None:
    """Show weak references, finalizers and cache eviction."""
    print("-- ref: a reference that does not keep the object alive")
    blob = Blob("a")
    ref = weakref.ref(blob, lambda r: print("  callback: blob died"))
    print("  ref() is blob:", ref() is blob)
    del blob
    print("  after del    :", ref())
    print("-- what cannot be weakly referenced")
    for value in (1, "text", [1], (1,), {}, Slotted()):
        try:
            weakref.ref(value)
            print(f"  {type(value).__name__:8} ok")
        except TypeError as error:
            print(f"  {type(value).__name__:8} {error}")
    print("-- finalize: cleanup that survives without __del__")
    victim = Blob("b")
    fin = weakref.finalize(victim, print, "  finalized:", "b")
    print("  alive:", fin.alive)
    del victim
    print("  alive:", fin.alive)
    kept = Blob("c")
    fin = weakref.finalize(kept, print, "  not printed")
    print("  detach:", fin.detach() is not None, "-> no callback ever")
    print("-- WeakValueDictionary: entries vanish with their values")
    cache: weakref.WeakValueDictionary[str, Blob] = (
        weakref.WeakValueDictionary()
    )
    one, two = Blob("one"), Blob("two")
    cache["one"], cache["two"] = one, two
    print("  keys:", sorted(cache))
    del two
    print("  keys:", sorted(cache))
    print("-- Searcher.documents over the corpus")
    pipeline = build_pipeline()
    _, index = load_index(CORPUS, pipeline)
    queries = [q for q in QUERIES.read_text("utf-8").splitlines() if q]
    shared = Searcher(index, pipeline=pipeline)
    copies = Searcher(
        index,
        pipeline=pipeline,
        load=lambda i: replace(index.documents[i]),
    )
    for query in queries:
        shared.search(query)
        copies.search(query)
    gc.collect()
    print(f"  queries            : {len(queries)}")
    print(f"  shared  hits/misses: {shared.doc_hits}/{shared.doc_misses}")
    print(f"  copies  hits/misses: {copies.doc_hits}/{copies.doc_misses}")
    print(f"  shared  cached now : {len(shared.documents)}")
    print(f"  copies  cached now : {len(copies.documents)}")
    held: Document = copies._document(0)
    print(f"  copies, held doc 0 : {sorted(copies.documents)}")
    del held
    gc.collect()
    print(f"  copies, released   : {sorted(copies.documents)}")


if __name__ == "__main__":
    main()
