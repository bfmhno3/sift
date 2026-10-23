"""SQLAlchemy 2.0 ORM: models, Session, unit of work, identity map."""

import tempfile
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Table, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)

from sift.storage.db import DocumentRow, open_db
from sift.storage.store import DB, update_index

MINI = Path("tests/fixtures/mini")
PIPELINE = ("mixed", "nfkc", "stopwords")


class Base(DeclarativeBase):
    """Declarative base of this lab's own models."""


post_tag = Table(
    "post_tag",
    Base.metadata,
    sa.Column("post_id", ForeignKey("post.id"), primary_key=True),
    sa.Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class PostRow(Base):
    """A post; tags is the many-to-many side."""

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    tags: Mapped[list[TagRow]] = relationship(
        secondary=post_tag, back_populates="posts"
    )


class TagRow(Base):
    """A tag, shared by many posts (lab only: Sift keeps tags as JSON)."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    posts: Mapped[list[PostRow]] = relationship(
        secondary=post_tag, back_populates="tags"
    )


def lab_models() -> None:
    """Unit of work and identity map on the lab's own models."""
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    statements: list[str] = []
    sa.event.listen(
        engine,
        "before_cursor_execute",
        lambda conn, cur, sql, *rest: statements.append(sql.split()[0]),
    )
    with Session(engine) as session:
        rust = TagRow(name="rust")
        post = PostRow(title="Ownership", tags=[rust])
        session.add(post)  # cascades to the tag through the relationship
        print("pending       :", len(session.new), "objects, 0 statements")
        session.flush()  # the unit of work orders the INSERTs
        print("after flush   :", statements)
        print("ids           :", post.id, rust.id)

        post.title = "Ownership and borrowing"
        print("dirty         :", [p.title for p in session.dirty])
        session.commit()
        print("commit flushed:", statements[-1])

        # identity map: one object per primary key per session
        first = session.get(PostRow, post.id)
        again = session.scalars(select(PostRow)).one()
        print("same object   :", first is again is post)
        print("back_populates:", [p.title for p in rust.posts])

        # a new TagRow named 'rust' breaks the unique constraint
        session.add(TagRow(name="rust"))
        try:
            session.flush()
        except sa.exc.IntegrityError as error:
            print("IntegrityError:", str(error.orig))
            session.rollback()
    engine.dispose()


def sift_models() -> None:
    """Query Sift's own DocumentRow in an index built in a temp dir."""
    with tempfile.TemporaryDirectory(prefix="sift-orm-") as tmp:
        update_index(MINI.resolve(), Path(tmp), PIPELINE)
        maker = open_db(Path(tmp) / DB)
        with maker() as session:
            stmt = (
                select(DocumentRow)
                .where(DocumentRow.category.is_not(None))
                .order_by(DocumentRow.published)
                .limit(3)
            )
            for row in session.scalars(stmt):
                print(f"{row.doc_id}  {row.published[:10]}  {row.title}")
                print(f"   tags {row.tags}  sha256 {row.sha256[:12]}")
            print("columns:", [c.name for c in DocumentRow.__table__.c])
        maker.kw["bind"].dispose()


def main() -> None:
    """Run both parts."""
    print("lab models")
    lab_models()
    print()
    print("Sift's DocumentRow")
    sift_models()


if __name__ == "__main__":
    main()
