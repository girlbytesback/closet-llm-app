from __future__ import annotations
from datetime import datetime
from fastapi import HTTPException

import uuid

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
    func
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


class DuplicatePhoto(HTTPException):
    """This user already has a photo under this filename.

    An HTTPException subclass rather than a plain one, so the unique constraint
    and any caller that forgets to catch it both produce the same 409 body
    rather than a 500.
    """

    def __init__(self, filename: str):
        super().__init__(status_code=409, detail=f"{filename} already exists")


def load_user_colors(table: Table, user_id: str) -> dict[str, list[str]]:
    """One user's rows, in the exact {filename: [hexes]} shape the JSON had."""
    query = select(table.c.filename, table.c.colors).where(table.c.user_id == user_id)
    with engine.connect() as conn:                 # borrow a pooled connection; returned on exit
        rows = conn.execute(query)
        return {filename: colors for filename, colors in rows}

def add_photo(
    table: Table,
    user_id: str,
    filename: str,
    colors: list[str],
    storage_key: str,
    photo_id: uuid.UUID | None = None,
) -> None:
    """Insert one row. Raises DuplicatePhoto if this user already has this filename."""
    values = dict(user_id=user_id, filename=filename, colors=colors, storage_key=storage_key)
    if photo_id is not None:
        values["id"] = photo_id
    try:
        with engine.begin() as conn:
            conn.execute(insert(table).values(**values))
    except IntegrityError:
        raise DuplicatePhoto(filename)


def delete_photo(table: Table, photo_id) -> None:
    with engine.begin() as conn:
        conn.execute(table.delete().where(table.c.id == photo_id))


def load_user_keys(table: Table, user_id: str) -> dict[str, str]:
    """{filename: storage_key} for one user — what the endpoints sign links from."""
    query = select(table.c.filename, table.c.storage_key).where(table.c.user_id == user_id)
    with engine.connect() as conn:
        return {filename: key for filename, key in conn.execute(query)}


def uploads_since(table: Table, user_id: str, since: datetime) -> int:
    """How many rows this user has added to this table since `since`."""
    query = (
        select(func.count())
        .select_from(table)
        .where(table.c.user_id == user_id, table.c.created_at >= since)
    )
    with engine.connect() as conn:
        return conn.execute(query).scalar_one()