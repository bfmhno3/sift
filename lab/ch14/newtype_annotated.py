"""NewType and Annotated: distinct ids, metadata on a type."""

from dataclasses import dataclass
from typing import Annotated, NewType, TypeAliasType, get_type_hints

DocId = NewType("DocId", int)
TermId = NewType("TermId", int)


@dataclass(frozen=True)
class Gt:
    """Metadata: the value must be greater than ``bound``."""

    bound: int


type Limit = Annotated[int, Gt(0)]


@dataclass
class Query:
    """A query; Annotated metadata is data, nothing checks it."""

    text: str
    limit: Limit = 10
    doc: Annotated[DocId, "the document to start from"] = DocId(0)


def title_of(doc_id: DocId) -> str:
    """Return a fake title; only a DocId is accepted."""
    return f"doc-{doc_id}"


def metadata(hint: object) -> tuple[object, ...]:
    """Return the Annotated metadata of hint, through type aliases.

    get_type_hints leaves ``type Limit = ...`` as a TypeAliasType, so
    unwrap ``__value__`` until an Annotated (or something else) shows.
    """
    while isinstance(hint, TypeAliasType):
        hint = hint.__value__
    return tuple(getattr(hint, "__metadata__", ()))


def check(obj: object) -> list[str]:
    """Read Gt(...) metadata and report fields that break it."""
    problems: list[str] = []
    hints = get_type_hints(type(obj), include_extras=True)
    for name, hint in hints.items():
        for meta in metadata(hint):
            value = getattr(obj, name)
            if isinstance(meta, Gt) and value <= meta.bound:
                problems.append(f"{name}={value} must be > {meta.bound}")
    return problems


def main() -> None:
    """Show that NewType is free at runtime and Annotated is data."""
    doc = DocId(7)
    print(title_of(doc), type(doc).__name__, doc == 7)
    print("limit=10:", check(Query("rust")))
    print("limit=0: ", check(Query("rust", limit=0)))
    print(Limit.__value__)


if __name__ == "__main__":
    main()
