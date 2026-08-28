import json
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic
from closetllm.images import image_block
from closetllm.color import validate_hex_value
from closetllm.config import (
    garment_clothing_model,
    color_palettes_model,
    garment_folder,
    color_palettes_folder,
    img_types,
    palette_hex_colors,
    garment_hex_colors,
)

_client = None


def client() -> Anthropic:
    """Build the API client on first use, not at import.

    Anthropic() reads the API key when it's constructed, so doing it at module
    level would mean `closetllm match` needs a key even though it never calls
    the API. This defers it until a call actually happens.
    """
    global _client
    if _client is None:
        _client = Anthropic()
    return _client

@dataclass(frozen=True)
class ExtractPhotoDetails:
    model: str
    prompt: str
    tool: dict
    json_data: Path
    colors_key: str  # which key in the tool result holds the hex codes

    @property
    def tool_name(self) -> str:
        # read the name back out of the tool so it can't drift out of sync
        return self.tool["name"]

palette_job = ExtractPhotoDetails(
    model=color_palettes_model,
    prompt="Return the two main colors in this photo as HEX codes",
    tool={
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
    },
    json_data=palette_hex_colors,
    colors_key="colors",
)

garment_job = ExtractPhotoDetails(
    model=garment_clothing_model,
    prompt=(
        "Return the single most dominant color of the clothing item in this photo as a HEX code. "
        "Ignore the background, the floor, the hanger, and other objects in photo that are not the clothing item"
    ),
    tool={
        "name": "extract_clothing_colors",
        "description": "Extract the dominant color of the clothing item as a HEX code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "The clothing item, e.g. 'linen button-down shirt'",
                },
                "color": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "description": "Dominant color of the clothing item as a HEX code, e.g. '#A85C37'",
                },
            },
            "required": ["item", "color"],
        },
    },
    json_data=garment_hex_colors,
    colors_key="color",
)

# one model call for one photo; returns whatever the tool's schema promised
# normalization occurs here, turns results to hex
def extract_colors(path: Path, job: ExtractPhotoDetails) -> dict:
    response = client().messages.create(
        model=job.model,
        max_tokens=1024,
        tools=[job.tool],
        tool_choice={"type": "tool", "name": job.tool_name},
        messages=[
            {"role": "user", "content": [image_block(path), {"type": "text", "text": job.prompt}]}
        ],
    )
    block = next((b for b in response.content if b.type == "tool_use"), None)
    if block is None:
        # tool_choice forces a call, so this means the reply was cut short
        raise RuntimeError(
            f"{path.name}: {job.tool_name} returned no tool_use block "
            f"(stop_reason={response.stop_reason}) — the reply may have hit max_tokens"
        )
    return block.input

# reads off disk; missing or empty file means nothing saved yet
def load_data(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    return json.loads(text) if text.strip() else {}

# saves hex values to json file, creating data/ the first time
def save_data(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

# walks the folder and fills in any photo we don't already have colors for
def run(folder: Path, job: ExtractPhotoDetails) -> dict:
    if not folder.is_dir():
        raise FileNotFoundError(f"no photos folder at {folder}")

    data = load_data(job.json_data)

    for photo in sorted(folder.iterdir()):
        if photo.suffix.lower() not in img_types:
            continue

        if photo.name in data:
            source = "saved"
        else:
            value = extract_colors(photo, job)[job.colors_key]
            # palettes give a list, clothes give one string — normalize to a list
            values = value if isinstance(value, list) else [value]
            # an empty list validates vacuously and saves clean, then blows up in
            # score_garment's min() on a later `match` — fail on the photo instead
            if not values:
                raise ValueError(f"{photo.name}: {job.tool_name} returned no colors")
            data[photo.name] = [validate_hex_value(v) for v in values]
            # save per photo so an interrupt doesn't throw away calls already paid for
            save_data(data, job.json_data)
            source = "new"

        print(f"{photo.name}: {', '.join(data[photo.name])} ({source})")

    return data

def run_color_palettes(folder: Path = color_palettes_folder) -> dict:
    return run(folder, palette_job)

def run_closet_colors(folder: Path = garment_folder) -> dict:
    return run(folder, garment_job)