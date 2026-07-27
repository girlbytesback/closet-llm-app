"""Turning an image file on disk into a content block the Messages API accepts."""

import base64
import io
from pathlib import Path

from PIL import Image

from closetllm.config import max_edge


def image_block(path: Path) -> dict:
    """Downscale the image and return it as a base64 JPEG content block."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_edge, max_edge))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buf.getvalue()).decode("utf-8"),
        },
    }
