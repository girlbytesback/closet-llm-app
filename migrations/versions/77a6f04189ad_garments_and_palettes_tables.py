"""garments and palettes tables

Revision ID: 77a6f04189ad
Revises: 
Create Date: 2026-09-21 13:47:16.630888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77a6f04189ad'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for name in ("garments", "palettes"):
        op.execute(f"""
            create table {name} (
              id          uuid primary key default gen_random_uuid(),
              user_id     text not null,
              filename    text not null,
              colors      text[] not null,
              storage_key text not null,
              created_at  timestamptz not null default now(),
              unique (user_id, filename)
            )
        """)
        op.execute(f"create index on {name} (user_id)")



def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop table palettes")
    op.execute("drop table garments")
