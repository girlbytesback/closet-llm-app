from pathlib import Path

from anthropic import Anthropic

from closetllm.config import garment_model, palette_model
from closetllm.images import image_block

client = Anthropic()

color_palette_prompt = "Return the two main colors in this photo as a single HEX code"

clothing_prompt = (
    "Extract the main colors of the clothing item in this photo as HEX codes. "
    "Ignore the background, skin, hair, and any surroundings."
)

color_pallete_tools = [
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
        model=garment_model,
        max_tokens=1024,
        tools=clothing_tools,
        tool_choice={"type": "tool", "name": "extract_clothing_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": clothing_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")


def extract_color_palette(path: Path) -> dict:
    response = client.messages.create(
        model=palette_model,
        max_tokens=1024,
        tools=palette_tools,
        tool_choice={"type": "tool", "name": "extract_colors"},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": palette_prompt}]}
        ],
    )
    return next(block.input for block in response.content if block.type == "tool_use")