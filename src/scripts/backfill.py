import mimetypes

from closetllm import db, storage
from closetllm.config import color_palettes_folder, web_garment_folder

user_id = "5c4e7f70-36bd-4d94-9ca8-dda29584f246"


def backfill(table, folder):
    keys = db.load_user_keys(table, user_id)       # {filename: storage_key}
    for filename, key in keys.items():
        local = folder / filename
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        storage.put(key, local.read_bytes(), content_type)
        print("uploaded", key)


backfill(db.garments, web_garment_folder)
backfill(db.palettes, color_palettes_folder)