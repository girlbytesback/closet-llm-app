import base64
from pathlib import Path
from anthropic import Anthropic

client = Anthropic()

COLOR_PALETTE_FOLDER = Path("color-palettes")
IMG_TYPES = {".jpeg": "image/jpeg", ".jpg": "image/jpeg"}

PROMPT = "Return the two main colors in this photo as HEX codes"

TOOLS = [
    {
        "name": "extract_colors",
        "description": "Extract two dominant colors from Pinterest photo as HEX codes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dominant color as HEX codes, e.g. '#A85C37'",
                }
            },
            "required": ["colors"]
        },
    }
]

def image_block(path: Path) -> dict:
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
          tools=TOOLS,
          tool_choice={"type": "tool", "name": "extract_colors"},
          messages=[{"role": "user", "content": [image_block(color), {"type": "text", "text": PROMPT}]}],
      )
    hex_codes = next(block.input["colors"] for block in response.content if block.type == "tool_use")
    print(f"{color.name}: {hex_codes}")  