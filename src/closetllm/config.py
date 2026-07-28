"""Settings that more than one module needs: where images live, which model each
extraction calls, and how large an image may be when it goes over the wire."""

from pathlib import Path

clothes_folder = Path("clothes")
color_palettes_folder = Path("color-palettes")

img_types = {".jpeg", ".jpg", ".png"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

clothing_model = "claude-opus-5"
color_palette_model = "claude-sonnet-5"
