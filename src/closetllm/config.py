from pathlib import Path

closet_clothing_folder = Path("clothes")
pinterest_board_folder = Path("color-palettes")

# Extracted palettes are saved here so each photo costs one model call ever. The
# model doesn't return the same HEX codes twice for the same image, so this file
# is also what keeps the palettes stable between runs.
pinterest_hex_colors = Path("data/colors.json")
closet_hex_colors = Path("data/clothes.json")

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

closet_clothing_model = "claude-opus-5"
pinterest_board_model = "claude-sonnet-5"