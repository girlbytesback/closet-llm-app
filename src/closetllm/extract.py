import json
from pathlib import Path

from anthropic import Anthropic

from closetllm.config import (
    closet_clothing_model,
    pinterest_board_model,
    closet_clothing_folder,
    pinterest_board_folder,
    img_types,
    pinterest_hex_colors,
    closet_hex_colors
)
from closetllm.images import image_block

client = Anthropic()

pinterest_board_prompt = "Return the two main colors in this photo as a single HEX code"
closet_clothing_prompt = (
    "Extract the main colors of the clothing item in this photo as HEX codes. "
    "Ignore the background, skin, hair, and any surroundings."
)

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
        model=closet_clothing_model,
        max_tokens=1024,
        tools=clothing_tools,
        tool_choice={"type": "tool", "name": "extract_clothing_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": closet_clothing_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")

#method to call correct claude model, passes in the prompt  
def extract_color_palette(path: Path) -> dict:
    response = client.messages.create(
        model=pinterest_board_model,
        max_tokens=1024,
        tools=color_palette_tools,
        tool_choice={"type": "tool", "name": "extract_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": pinterest_board_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")


#reads the saved palettes off disk; missing or empty file means nothing saved yet
def load_palettes() -> dict:
    if not pinterest_hex_colors.exists():
        return {}
    text = pinterest_hex_colors.read_text()
    return json.loads(text) if text.strip() else {}

def load_closet() -> dict:
    if not closet_hex_colors.exists():
        return {}
    text = closet_hex_colors.read_text()
    return json.loads(text) if text.strip() else {}

#writes the palettes back to disk, creating data/ the first time
def save_palettes(palettes: dict) -> None:
    pinterest_hex_colors.parent.mkdir(parents=True, exist_ok=True)
    pinterest_hex_colors.write_text(json.dumps(palettes, indent=2, sort_keys=True) + "\n")

def save_closet(closet: dict) -> None:
    closet_hex_colors.parent.mkdir(parents=True, exist_ok=True)
    closet_hex_colors.write_text(json.dumps(closet, indent=2, sort_keys=True) + "\n")

#walks the folder and fills in any photo we don't already have colors for
def run_color_palettes(folder: Path = pinterest_board_folder) -> dict:
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

def run_closet_colors(folder: Path = closet_clothing_folder) -> dict:
    closet = load_closet()

    for photo in sorted(folder.iterdir()):
        if photo.suffix.lower() not in img_types:
            continue

        if photo.name not in closet:
            closet[photo.name] = extract_clothing_colors(photo)["colors"]
            save_closet(closet)
            source = "NEW"
        else:
            source = "SAVED"

        print(f"{photo.name}: {', '.join(closet[photo.name])} ({source})")

    return closet