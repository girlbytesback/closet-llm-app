from __future__ import annotations
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import Table

from closetllm import db, storage
from closetllm.color import validate_hex_value
from closetllm.config import img_types
from closetllm.extract import ExtractPhotoDetails, extract_colors
from closetllm.images import web_copy

CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

def remove_broken_photo(dest: Path, web_folder: Path | None) -> None:
    #delete photo + web copy to prevent crash (if JSON entry exists but garment doesnt)
    dest.unlink(missing_ok=True)
    if web_folder:
        (web_folder / dest.name).unlink(missing_ok=True)

# INGEST() WILL:
# 1. write the photo to garments/
# 2. make the web copy in assets/garments/
# 3. call Claude               <- try/except was only here
# 4. check the list isn't empty
# 5. validate each hex
# 6. write the entry to garments.json

def ingest(
    file: UploadFile,
    job: ExtractPhotoDetails,
    table: Table,
    prefix: str,          # "garments" or "palettes" — the first part of the key
    shrink: bool,         # True for garments: store the small web copy, not the original
    user_id: str,
) -> dict:
    file_name = Path(file.filename).name
    suffix = Path(file_name).suffix.lower()
    if suffix not in img_types:
        raise HTTPException(status_code=415, detail=f"unsupported type {suffix}")

    with tempfile.TemporaryDirectory() as tmp:          # deleted when this block exits, success or not
        work = Path(tmp)
        original = work / file_name
        with original.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        value = extract_colors(original, job)[job.colors_key]
        values = value if isinstance(value, list) else [value]
        if not values:
            raise HTTPException(status_code=502, detail=f"{file_name}: the model returned no colors")
        hexes = [validate_hex_value(v) for v in values]

        if shrink:
            web_copy(original, work / "web")
            stored = work / "web" / file_name
        else:
            stored = original

        photo_id = uuid.uuid4()
        key = f"{prefix}/{user_id}/{photo_id}{suffix}"
        db.add_photo(table, user_id, file_name, hexes, storage_key=key, photo_id=photo_id)   # 409 here

        try:
            storage.put(key, stored.read_bytes(), CONTENT_TYPES[suffix])
        except Exception:
            db.delete_photo(table, photo_id)             # undo the row so a retry isn't a 409
            raise
    return {"name": file_name, "colors": hexes}