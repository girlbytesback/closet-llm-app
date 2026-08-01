import json
from pathlib import Path

from anthropic import Anthropic

from closetllm.config import (
    clothing_model,
    color_palette_model,
    color_palettes_folder,
    img_types,
    palettes_file,
)
from closetllm.images import image_block

client = Anthropic()

color_palette_prompt = "Return the two main colors in this photo as a single HEX code"
clothing_prompt = (
    "Extract the main colors of the clothing item in this photo as HEX codes. "
    "Ignore the background, skin, hair, and any surroundings."
)

hex_color_palette = {}

color_palette_tools = [
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
            "required": ["colors"],
        },
    }
]

clothing_tools = [
    {
        "name": "extract_clothing_colors",
        "description": "Extract the dominant colors of the clothing item as HEX codes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "The clothing item, e.g. 'linen button-down shirt'",
                },
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dominant colors of the clothing item as HEX codes, e.g. '#A85C37'",
                },
            },
            "required": ["item", "colors"],
        },
    }
]

def extract_clothing_colors(path: Path) -> dict:
    """Identify the garment in the photo. Returns {"item": str, "colors": list}."""
    response = client.messages.create(
        model=clothing_model,
        max_tokens=1024,
        tools=clothing_tools,
        tool_choice={"type": "tool", "name": "extract_clothing_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": clothing_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")

#method to call correct claude model, passes in the prompt  
def extract_color_palette(path: Path) -> dict:
    response = client.messages.create(
        model=color_palette_model,
        max_tokens=1024,
        tools=color_palette_tools,
        tool_choice={"type": "tool", "name": "extract_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": color_palette_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")


#reads the saved palettes off disk; missing or empty file means nothing saved yet
def load_palettes() -> dict:
    if not palettes_file.exists():
        return {}
    text = palettes_file.read_text()
    return json.loads(text) if text.strip() else {}


#writes the palettes back to disk, creating data/ the first time
def save_palettes(palettes: dict) -> None:
    palettes_file.parent.mkdir(parents=True, exist_ok=True)
    palettes_file.write_text(json.dumps(palettes, indent=2, sort_keys=True) + "\n")


#walks the folder and fills in any photo we don't already have colors for
def run_color_palettes(folder: Path = color_palettes_folder) -> dict:
    palettes = load_palettes()

    for photo in sorted(folder.iterdir()):
        if photo.suffix.lower() not in img_types:
            continue

        if photo.name not in palettes:
            palettes[photo.name] = extract_color_palette(photo)["colors"]
            # save per photo so an interrupt doesn't throw away calls already paid for
            save_palettes(palettes)
            source = "new"
        else:
            source = "saved"

        print(f"{photo.name}: {', '.join(palettes[photo.name])} ({source})")

    return palettes