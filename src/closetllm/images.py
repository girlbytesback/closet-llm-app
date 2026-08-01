"""Turning an image file on disk into a content block the Messages API accepts."""

import base64
import io
from pathlib import Path

from PIL import Image

from closetllm.config import max_edge


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
