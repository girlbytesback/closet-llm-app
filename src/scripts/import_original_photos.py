"""upload the photos behind already-imported rows, then point each row at its key."""
import uuid

from sqlalchemy import select, update

from closetllm import db, storage
from closetllm.config import color_palettes_folder, web_garment_folder
from closetllm.ingest import CONTENT_TYPES

USER_ID = "5c4e7f70-36bd-4d94-9ca8-dda29584f246"

for table, prefix, folder in (
    (db.garments, "garments", web_garment_folder),      # the small web copies
    (db.palettes, "palettes", color_palettes_folder),
):
    with db.engine.connect() as conn:
        rows = conn.execute(select(table.c.id, table.c.filename).where(table.c.user_id == USER_ID)).all()

    for row_id, filename in rows:
        path = folder / filename
        if not path.exists():
            print(f"skip {filename}: no file")
            continue
        suffix = path.suffix.lower()
        key = f"{prefix}/{USER_ID}/{uuid.uuid4()}{suffix}"
        storage.put(key, path.read_bytes(), CONTENT_TYPES[suffix])
        with db.engine.begin() as conn:
            conn.execute(update(table).where(table.c.id == row_id).values(storage_key=key))
        print(f"{prefix}: {filename} -> {key}")


