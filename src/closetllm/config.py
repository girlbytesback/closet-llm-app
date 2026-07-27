"""Settings that more than one module needs: where images live, which model each
extraction calls, and how large an image may be when it goes over the wire."""

from pathlib import Path

# Folders the CLI scans when no path is given, relative to the repo root.
clothes_folder = Path("clothes")
palettes_folder = Path("color-palettes")

# Extensions we're willing to open. Everything is re-encoded to JPEG before
# upload, so this is about what Pillow can read, not what the API accepts.
img_types = {".jpeg", ".jpg", ".png", ".webp"}

# Claude caps images at 5MB and downscales anything over 1568px on the long edge
# anyway, so shrink before sending — the phone photos in clothes/ are well over both.
max_edge = 1568

# These were different in the two original scripts and are kept that way.
garment_model = "claude-opus-5"
palette_model = "claude-sonnet-5"
