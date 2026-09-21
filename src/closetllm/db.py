from fastapi import HTTPException
from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError

from closetllm.config import database_url

# The connection pool: created once at import, shared by every request.
# Like a DataSource. pool_pre_ping tests a connection before handing it out,
# so a dropped idle connection reconnects instead of erroring.
engine = create_engine(database_url, pool_pre_ping=True)

meta = MetaData()   # registry that holds the table definitions below


def _photos_table(name: str) -> Table:
    """garments and palettes have the same shape; define it once."""
    return Table(
        name,
        meta,
        Column("id", UUID, primary_key=True, server_default=text("gen_random_uuid()")),
        Column("user_id", Text, nullable=False, index=True),
        Column("filename", Text, nullable=False),
        Column("colors", ARRAY(Text), nullable=False),
        Column("storage_key", Text, nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        UniqueConstraint("user_id", "filename"),
    )

garments = _photos_table("garments")
palettes = _photos_table("palettes")

def load_user_colors(table: Table, user_id: str) -> dict[str, list[str]]:
    """One user's rows, in the exact {filename: [hexes]} shape the JSON had."""
    query = select(table.c.filename, table.c.colors).where(table.c.user_id == user_id)
    with engine.connect() as conn:                 # borrow a pooled connection; returned on exit
        rows = conn.execute(query)
        return {filename: colors for filename, colors in rows}


def add_photo(table: Table, user_id: str, filename: str, colors: list[str], storage_key: str) -> None:
    """Insert one row. Raises 409 if this user already has this filename."""
    row = insert(table).values(
        user_id=user_id, filename=filename, colors=colors, storage_key=storage_key
    )
    try:
        with engine.begin() as conn:               # transaction: commits on clean exit, rolls back on exception
            conn.execute(row)
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"{filename} already exists")