#VARIABLES AND CONSTANTS
from pathlib import Path

clothes_folder = Path("clothes")
color_palettes_folder = Path("color-palettes")

# Extracted palettes are saved here so each photo costs one model call ever. The
# model doesn't return the same HEX codes twice for the same image, so this file
# is also what keeps the palettes stable between runs.
palettes_file = Path("data/colors.json")

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

clothing_model = "claude-opus-5"
color_palette_model = "claude-sonnet-5"
