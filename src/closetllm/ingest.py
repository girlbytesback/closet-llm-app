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

# INGEST() WILL:
# 1. check the file type
# 2. save the upload into a temp folder, which is emptied on the way out —
#    nothing an upload writes survives locally, so there is no orphan to sweep
# 3. call Claude, then check the list isn't empty and validate each hex
# 4. pick what to upload (the web copy for garments, the original otherwise)
# 5. insert the row  (a duplicate stops here)
# 6. upload to the bucket, undoing the row if that fails

def ingest(file: UploadFile, job: ExtractPhotoDetails, table: Table,
           user_id: str, needs_web_copy: bool) -> dict:
    # 1. check the type
    file_name = Path(file.filename).name
    if Path(file_name).suffix.lower() not in img_types:
        raise HTTPException(status_code=415, detail="unsupported type")

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
        storage_key = f"{user_id}/{file_name}"
        try:
            db.add_photo(table, user_id, file_name, hexes, storage_key, photo_id)
        except db.DuplicatePhoto:
            raise HTTPException(status_code=409, detail=f"{file_name} already exists")

        # 6. upload; undo the row if it fails
        try:
            storage.upload(storage_key, to_upload)
        except Exception:
            db.delete_photo(table, user_id, photo_id)
            raise

    return {"name": file_name, "colors": hexes}    