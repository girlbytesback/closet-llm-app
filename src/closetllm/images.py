"""Turning an image file on disk into a content block the Messages API accepts."""

import base64
import io
from pathlib import Path

from PIL import Image

from closetllm.config import max_edge

def web_copy(photo: Path, out_dir: Path) -> tuple[int, int]:
    """Write a downscaled copy of `photo` into `out_dir`. Returns (before, after) bytes."""
    img = Image.open(photo)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, WHITE)
        flat.paste(img, mask=img.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    # thumbnail() scales in place, preserves aspect ratio, and never upscales
    img.thumbnail((web_max_edge, web_max_edge))

    # The filename must match the key in clothes.json exactly — the UI builds
    # its src as url_prefix + filename, so a renamed file is a broken image.
    out_path = out_dir / photo.name
    img.save(out_path, format="JPEG", quality=85, optimize=True)

    return photo.stat().st_size, out_path.stat().st_size


def image_block(path: Path) -> dict:
    #load image from disk and convert to RGB
    img = Image.open(path).convert("RGB")
    #shrink
    img.thumbnail((max_edge, max_edge))
    #resaves to memory locally?
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    #saves to RAM, not disk. 

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buf.getvalue()).decode("utf-8"),
        },
    }


