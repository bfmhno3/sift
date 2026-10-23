"""SQLAlchemy 2.0 Core: Table, insert(), select(), compiled SQL."""

import sqlalchemy as sa
from sqlalchemy import func, insert, select

from sift.cli import CORPUS
from sift.corpus import iter_documents

metadata = sa.MetaData()
posts = sa.Table(
    "posts",
    metadata,
    sa.Column("doc_id", sa.Integer, primary_key=True),
    sa.Column("title", sa.String, nullable=False),
    sa.Column("category", sa.String),
    sa.Column("n_chars", sa.Integer, nullable=False),
)


def main() -> None:
    """Create a table, fill it from the corpus, query it."""
    print("sqlalchemy", sa.__version__)
    engine = sa.create_engine("sqlite://")  # in memory
    metadata.create_all(engine)
    rows = [
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "category": doc.category,
            "n_chars": len(doc.body),
        }
        for doc in iter_documents(CORPUS)
    ]

    # Core statements are objects: printing one shows the SQL text
    stmt = insert(posts)
    print(stmt)
    with engine.begin() as conn:  # commits at the end of the block
        result = conn.execute(stmt, rows)  # a list means executemany
        print("inserted", result.rowcount, "rows")

    longest = (
        select(posts.c.title, posts.c.n_chars)
        .where(posts.c.category == "Tutorial")
        .order_by(posts.c.n_chars.desc())
        .limit(3)
    )
    print()
    print(longest)
    print("params:", longest.compile().params)
    with engine.connect() as conn:  # no commit: read only
        for row in conn.execute(longest):
            print(f"  {row.n_chars:>6}  {row.title}")

    per_category = (
        select(
            posts.c.category,
            func.count().label("posts"),
            func.round(func.avg(posts.c.n_chars)).label("mean_chars"),
        )
        .group_by(posts.c.category)
        .order_by(func.count().desc())
    )
    print()
    with engine.connect() as conn:
        for row in conn.execute(per_category).mappings():
            print(dict(row))
        # the value is bound, whatever it contains
        hostile = "x' OR '1'='1"
        found = conn.execute(
            select(func.count()).where(posts.c.title == hostile)
        ).scalar_one()
        print("title == hostile string ->", found, "rows")

    # a transaction that raises is rolled back
    try:
        with engine.begin() as conn:
            conn.execute(posts.delete())
            raise RuntimeError("stop")
    except RuntimeError:
        pass
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(posts))
        print("rows after the rolled back delete:", count.scalar_one())
    engine.dispose()


if __name__ == "__main__":
    main()
