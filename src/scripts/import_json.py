"""my old clothes"""
from closetllm import db
from closetllm.config import garment_hex_colors, palette_hex_colors
from closetllm.extract import load_data

USER_ID = "5c4e7f70-36bd-4d94-9ca8-dda29584f246"  

for table, path in ((db.garments, garment_hex_colors), (db.palettes, palette_hex_colors)):
    for filename, colors in load_data(path).items():
        db.add_photo(table, USER_ID, filename, colors, storage_key=filename)
        print(f"{table.name}: {filename} {colors}")