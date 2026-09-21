from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import Table

from closetllm import db
from closetllm.color import validate_hex_value
from closetllm.config import img_types
from closetllm.extract import ExtractPhotoDetails, extract_colors
from closetllm.images import web_copy

def remove_broken_photo(dest: Path, web_folder: Path | None) -> None:
    #delete photo + web copy to prevent crash (leftovers with no row behind them)
    dest.unlink(missing_ok=True)
    if web_folder:
        (web_folder / dest.name).unlink(missing_ok=True)

# INGEST() WILL:
# 1. refuse a filename this user already has
# 2. write the photo to garments/ under a staging name
# 3. call Claude
# 4. check the list isn't empty
# 5. validate each hex
# 6. make the web copy in assets/garments/, also staged
# 7. insert the row                <- the unique constraint is the real 409
# 8. move both staged files into place
#
# Nothing lands under its final name until the row is in. Every step before
# that writes to "<name>.part", so a failure anywhere — and a 409 in
# particular — cannot touch the photo a previous upload already saved.

def ingest(
    file: UploadFile,
    job: ExtractPhotoDetails,
    table: Table,                 # db.garments or db.palettes — replaces the json_data routing
    folder: Path,
    web_folder: Path | None,
    user_id: str,
) -> dict:
    file_name = Path(file.filename).name
    suffix = Path(file_name).suffix.lower()
    if suffix not in img_types:
        raise HTTPException(status_code=415, detail=f"unsupported type {suffix or file_name}")

    # A filename this user already has is refused before the model is paid for.
    # add_photo's unique constraint is still the authority — two requests can
    # both pass this check — but the common case costs a read, not a call.
    if file_name in db.load_user_colors(table, user_id):
        raise HTTPException(status_code=409, detail=f"{file_name} already exists")

    dest = folder / file_name
    staged = folder / f".{file_name}.part"
    folder.mkdir(parents=True, exist_ok=True)
    with staged.open("wb") as out: # wb = write binary
        shutil.copyfileobj(file.file, out)

    try:
        value = extract_colors(staged, job)[job.colors_key]
        values = value if isinstance(value, list) else [value]
        if not values:
            raise HTTPException(status_code=502, detail=f"{file_name}: the model returned no colors")

        hexes = [validate_hex_value(v) for v in values]

        if web_folder:
            web_folder.mkdir(parents=True, exist_ok=True)
            # web_copy names its output after the file it is given, so handing it
            # the staged photo stages the web copy under the same ".part" name.
            web_copy(staged, web_folder)

        db.add_photo(table, user_id, file_name, hexes, storage_key=file_name)
    except Exception:
        remove_broken_photo(staged, web_folder)
        raise

    staged.replace(dest)
    if web_folder:
        (web_folder / staged.name).replace(web_folder / file_name)
    return {"name": file_name, "colors": hexes}
