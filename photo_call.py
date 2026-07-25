import base64
from pathlib import Path
from anthropic import Anthropic

client = Anthropic()

COLOR_PALETTE_FOLDER = Path("color-palettes")
IMG_TYPES = {".jpeg": "image/jpeg", ".jpg": "image/jpeg"}

PROMPT = "Return the two main colors in this photo as HEX codes"

def extract_colors(path: Path) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": IMG_TYPES[path.suffix.lower()],
            "data": base64.standard_b64encode(path.read_bytes()).decode("utf-8"),
        }
    }

for color in sorted(COLOR_PALETTE_FOLDER.iterdir()):
    #if color palette image is not of type .jpeg for whatever reason, ignore
    if color.suffix.lower() not in IMG_TYPES:
          continue
    
    response = client.messages.create(
          model="claude-sonnet-5",
          max_tokens=1024,
          messages=[{"role": "user", "content": [extract_colors(color), {"type": "text", "text": PROMPT}]}],
      )
    hex_codes = next(hex_color_value.text for hex_color_value in response.content if hex_color_value.type == "text")
    print(f"{color.name}: {hex_codes}")
