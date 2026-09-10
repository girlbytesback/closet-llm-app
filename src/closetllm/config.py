import os
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]

# Data location is overridable so a container can mount it elsewhere.
# Everything downstream is derived from this one directory.
data_dir = Path(os.environ.get("CLOSETLLM_DATA_DIR", project_root / "data"))

palette_hex_colors = data_dir / "colors.json"
garment_hex_colors = data_dir / "garments.json"

# Photo source folders — also overridable, same reasoning.
garment_folder = Path(os.environ.get("CLOSETLLM_GARMENT_DIR", project_root / "garments"))
color_palettes_folder = Path(os.environ.get("CLOSETLLM_PALETTE_DIR", project_root / "color-palettes"))

# Log verbosity, consumed in Phase 6's middleware.
log_level = os.environ.get("CLOSETLLM_LOG_LEVEL", "INFO")

# Derived from the two files above exists bc the browser can't run Python.
# It lands inside the UI app because that's the only place Vite will import
# from — it's a build input for the frontend, so it lives with the frontend.
palette_matches = project_root / "src/ui/src/data/matches.json"

# Where the browser will find the photos. Python owns these so the UI never has
# to know how the images get served — it just renders the src it's handed.
# src/ui/public/ symlinks both folders, which is what makes these paths resolve.
garment_url_prefix = "/garments"
palette_url_prefix = "/color-palettes"

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in garments/ are well over both.
max_edge = 1568

garment_clothing_model = "claude-opus-5"
color_palettes_model = "claude-sonnet-5"