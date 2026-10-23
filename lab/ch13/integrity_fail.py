"""Insert two rows with the same primary key: IntegrityError."""

# error: sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE
# constraint failed: post.id
# [SQL: INSERT INTO post (id, title) VALUES (?, ?)]
# [parameters: (1, 'second')]
# (Background on this error at: https://sqlalche.me/e/20/gkpj)

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """Declarative base of this lab's model."""


class PostRow(Base):
    """A post identified by a primary key the caller chooses."""

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    title: Mapped[str]


def main() -> None:
    """Commit one post, then try to commit another with the same id."""
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(PostRow(id=1, title="first"))
        session.commit()
    with Session(engine) as session:  # a new session: empty identity map
        session.add(PostRow(id=1, title="second"))
        session.commit()


if __name__ == "__main__":
    main()
