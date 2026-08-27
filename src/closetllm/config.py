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

# Derived from the two files above exists bc the browser can't run Python.
# It lands inside the UI app because that's the only place Vite will import
# from — it's a build input for the frontend, so it lives with the frontend.
palette_matches = project_root / "src/ui/src/data/matches.json"

# Where the browser will find the photos. Python owns these so the UI never has
# to know how the images get served — it just renders the src it's handed.
# src/ui/public/ symlinks both folders, which is what makes these paths resolve.
garment_url_prefix = "/clothes"
palette_url_prefix = "/color-palettes"

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

garment_clothing_model = "claude-opus-5"
color_palettes_model = "claude-sonnet-5"