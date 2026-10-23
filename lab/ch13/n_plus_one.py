"""The N+1 query problem: lazy loading against eager loading."""

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Table, event, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    joinedload,
    mapped_column,
    raiseload,
    relationship,
    selectinload,
)

from sift.cli import CORPUS
from sift.corpus import iter_documents


class Base(DeclarativeBase):
    """Declarative base of this lab's models."""


post_tag = Table(
    "post_tag",
    Base.metadata,
    sa.Column("post_id", ForeignKey("post.id"), primary_key=True),
    sa.Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class TagRow(Base):
    """A tag."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class PostRow(Base):
    """A post; tags loads lazily, one SELECT per post, by default."""

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    tags: Mapped[list[TagRow]] = relationship(secondary=post_tag)


def fill(engine: sa.Engine) -> int:
    """Insert every corpus post with its tags; return the post count."""
    with Session(engine) as session:
        tags: dict[str, TagRow] = {}
        for doc in iter_documents(CORPUS):
            row_tags = [
                tags.setdefault(name, TagRow(name=name)) for name in doc.tags
            ]
            session.add(PostRow(id=doc.doc_id, title=doc.title, tags=row_tags))
        session.commit()
        return session.query(PostRow).count()


def count_statements(engine: sa.Engine, load: object | None) -> list[str]:
    """Return the SQL of every statement run while listing all tags."""
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with Session(engine) as session:
            stmt = select(PostRow).order_by(PostRow.id)
            if load is not None:
                stmt = stmt.options(load)
            posts = session.scalars(stmt).unique().all()
            total = sum(len(post.tags) for post in posts)
            print(f"  {len(posts)} posts, {total} tag links read")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return statements


def main() -> None:
    """Load all posts and their tags four ways; count the statements."""
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    n_posts = fill(engine)
    print(f"{n_posts} posts in the database")
    strategies = [
        ("lazy (the default)", None),
        ("selectinload", selectinload(PostRow.tags)),
        ("joinedload", joinedload(PostRow.tags)),
    ]
    for name, load in strategies:
        print(name)
        statements = count_statements(engine, load)
        print(f"  statements: {len(statements)}")
        print("  first:", " ".join(statements[0].split())[:90])
        if len(statements) > 1:
            print("  last :", " ".join(statements[-1].split())[:90])
    print("raiseload: touching a relationship that was not loaded")
    with Session(engine) as session:
        post = session.scalars(
            select(PostRow).options(raiseload(PostRow.tags)).limit(1)
        ).one()
        try:
            list(post.tags)
        except sa.exc.InvalidRequestError as error:
            print(f"  {type(error).__name__}: {error}")
    engine.dispose()


if __name__ == "__main__":
    main()
