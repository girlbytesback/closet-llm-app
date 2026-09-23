from __future__ import annotations
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import Table

from closetllm import db, storage
from closetllm.color import validate_hex_value
from closetllm.config import img_types
from closetllm.extract import ExtractPhotoDetails, extract_colors
from closetllm.images import web_copy

CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

# INGEST() WILL:
# 1. check the file type
# 2. save the upload into a temp folder, which is emptied on the way out —
#    nothing an upload writes survives locally, so there is no orphan to sweep
# 3. call Claude, then check the list isn't empty and validate each hex
# 4. pick what to upload (the web copy for garments, the original otherwise)
# 5. insert the row  (a duplicate stops here)
# 6. upload to the bucket, undoing the row if that fails


def storage_key_for(table: Table, user_id: str, photo_id: uuid.UUID, suffix: str) -> str:
    """Where this photo's bytes live in the bucket.

    The row's own id, not the filename: the bucket is one flat namespace, two
    people are each allowed a shirt.jpeg, and the same person is allowed one in
    each table. The table name leads so a prefix listing is per-kind, and the
    user id comes next so a policy can be written against the path.
    """
    return f"{table.name}/{user_id}/{photo_id}{suffix}"


def ingest(file: UploadFile, job: ExtractPhotoDetails, table: Table,
           user_id: str, needs_web_copy: bool) -> dict:
    # 1. check the type
    file_name = Path(file.filename).name
    suffix = Path(file_name).suffix.lower()
    if suffix not in img_types:
        raise HTTPException(status_code=415, detail="unsupported type")

    since = datetime.now(timezone.utc) - timedelta(days=1)
    if db.uploads_since(table, user_id, since) >= DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="daily upload limit reached, try again tomorrow")

    with tempfile.TemporaryDirectory() as tmp:
        # 2. save the upload to the temp folder
        tmp = Path(tmp)
        original = tmp / file_name
        with original.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        # 3. get the colors
        value = extract_colors(original, job)[job.colors_key]
        values = value if isinstance(value, list) else [value]
        if not values:
            raise HTTPException(status_code=502, detail=f"{file_name}: the model returned no colors")
        hexes = [validate_hex_value(v) for v in values]

        # 4. pick the file to upload
        if needs_web_copy:
            web_folder = tmp / "web"
            web_folder.mkdir()
            web_copy(original, web_folder)
            to_upload = web_folder / file_name
        else:
            to_upload = original

        # 5. insert the row (duplicates stop here)
        photo_id = uuid.uuid4()
        storage_key = storage_key_for(table, user_id, photo_id, suffix)
        db.add_photo(table, user_id, file_name, hexes, storage_key, photo_id)

        # 6. upload; undo the row if it fails
        try:
            storage.put_file(storage_key, to_upload)
        except Exception:
            db.delete_photo(table, photo_id)
            raise

    return {"name": file_name, "colors": hexes}
