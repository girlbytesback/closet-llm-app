from __future__ import annotations

import shutil
from closetllm.config import img_types
from closetllm.extract import ExtractPhotoDetails, extract_colors, garment_job, palette_job, load_data, save_data
from closetllm.color import validate_hex_value
from closetllm.images import web_copy
from pathlib import Path
from fastapi import HTTPException, UploadFile


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

def ingest(file: UploadFile, job: ExtractPhotoDetails, folder: Path, web_folder: Path | None) -> dict:
    file_name = Path(file.filename).name
    if Path(file_name).suffix.lower() not in img_types:
        raise HTTPException(status_code=415, detail="unsupported type")
    dest = folder / file_name
    if dest.exists():
        raise HTTPException(status_code=409, detail=f"{file_name} already exists")

    folder.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out: # wb = write binary
        shutil.copyfileobj(file.file, out)
        
    try:
        if web_folder:
            web_folder.mkdir(parents=True, exist_ok=True)
            web_copy(dest, web_folder)

        value = extract_colors(dest, job)[job.colors_key]
        values = value if isinstance(value, list) else [value]
        if not values:
            raise HTTPException(status_code=502, detail=f"{file_name}: the model returned no colors")

        hexes = [validate_hex_value(v) for v in values]
        data = load_data(job.json_data)
        data[file_name] = hexes
        save_data(data, job.json_data)
    except Exception:
        remove_broken_photo(dest, web_folder)
        raise
    return {"name": file_name, "colors": hexes}