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