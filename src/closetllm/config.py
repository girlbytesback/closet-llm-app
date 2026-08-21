from pathlib import Path

# Anchored to the repo root (this file lives at src/closetllm/config.py) so the
# CLI works from any directory, not just wherever the folders happen to be relative.
project_root = Path(__file__).resolve().parents[2]

garment_folder = project_root / "clothes"
color_palettes_folder = project_root / "color-palettes"

# Extracted palettes are saved here so each photo costs one model call ever. The
# model doesn't return the same HEX codes twice for the same image, so this file
# is also what keeps the palettes stable between runs.
palette_hex_colors = project_root / "data/colors.json"
garment_hex_colors = project_root / "data/clothes.json"

# Derived from the two files above — pure arithmetic, free to rebuild. It exists
# only because the browser can't run Python.
palette_matches = project_root / "data/matches.json"

# Where the browser will find the garment photos. Python owns this so the UI
# never has to know how the images get served.
garment_url_prefix = "/clothes"

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

garment_clothing_model = "claude-opus-5"
color_palettes_model = "claude-sonnet-5"