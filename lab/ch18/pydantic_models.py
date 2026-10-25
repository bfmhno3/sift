"""pydantic v2: fields, defaults, Field, validators, dump, strict.

A ``Hit`` model with the same rules as the settings of Sift, then the
tools that every model has: ``model_dump``, ``model_dump_json``,
``model_validate_json`` and the difference between lax and strict
coercion.
"""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)


class Hit(BaseModel):
    """One search hit; the rules live in the annotations."""

    model_config = ConfigDict(frozen=True)

    doc_id: Annotated[int, Field(ge=0)]
    title: str = Field(min_length=1, max_length=120)
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    path: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        """Strip the spaces around the title; reject a blank one."""
        value = value.strip()
        if not value:
            raise ValueError("title is blank")
        return value

    @model_validator(mode="after")
    def tags_are_unique(self) -> Hit:
        """Reject a tag that appears twice."""
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("tags repeat")
        return self


class Counts(BaseModel):
    """The same field, lax by default and strict on request."""

    lax: int
    strict: StrictInt


def try_hit(**data: object) -> None:
    """Build a Hit; print it or the first error."""
    try:
        print("  ok:", Hit(**data))
    except ValidationError as error:
        first = error.errors(include_url=False)[0]
        print(f"  error at {first['loc']}: {first['msg']}")


def main() -> None:
    """Show the model at work."""
    print("defaults:")
    try_hit(doc_id=1, title="  Rust lifetimes  ")
    print("lax coercion (str to int and float):")
    try_hit(doc_id="7", title="x", score="1.5")
    print("constraints:")
    try_hit(doc_id=-1, title="x")
    try_hit(doc_id=1, title="x" * 121)
    print("validators:")
    try_hit(doc_id=1, title="   ")
    try_hit(doc_id=1, title="x", tags=["a", "a"])
    print("not a number:")
    try_hit(doc_id="seven", title="x")

    hit = Hit(doc_id=3, title="Tea", score=2.5, tags=["drink"])
    print("model_dump:     ", hit.model_dump())
    print("model_dump_json:", hit.model_dump_json())
    print("exclude_none:   ", hit.model_dump(exclude_none=True))
    again = Hit.model_validate_json(hit.model_dump_json())
    print("round trip equal:", again == hit)
    print("frozen:", end=" ")
    try:
        hit.doc_id = 4
    except ValidationError as error:
        print(error.errors(include_url=False)[0]["type"])

    print("strict:")
    print("  ", Counts(lax="5", strict=5))
    try:
        Counts(**{"lax": 1, "strict": "5"})
    except ValidationError as error:
        print("  ", error.errors(include_url=False)[0]["msg"])
    print("  ", Counts.model_validate({"lax": "5", "strict": 5}, strict=False))
    try:
        Counts.model_validate({"lax": "5", "strict": 5}, strict=True)
    except ValidationError as error:
        print("   strict=True:", error.errors(include_url=False)[0]["msg"])


if __name__ == "__main__":
    main()
