from sqlalchemy import update

from closetllm import db

OLD = "PASTE-YOUR-UUID-HERE"
NEW = "5c4e7f70-36bd-4d94-9ca8-dda29584f246"

with db.engine.begin() as conn:
    for table in (db.garments, db.palettes):
        result = conn.execute(update(table).where(table.c.user_id == OLD).values(user_id=NEW))
        print(f"{table.name}: {result.rowcount} rows updated")