import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from anthropic import Anthropic
from closetllm.images import image_block
from closetllm.config import (
    closet_clothing_model,
    pinterest_board_model,
    closet_clothing_folder,
    pinterest_board_folder,
    img_types,
    pinterest_hex_colors,
    closet_hex_colors,
)

client = Anthropic()
regex_hex = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

@dataclass(frozen=True)
class ExtractPhotoDetails:
    model: str
    prompt: str
    tool: dict
    json_data: Path

    @property
    def tool_name(self) -> str:
        # read the name back out of the tool so it can't drift out of sync
        return self.tool["name"]

palette_job = ExtractPhotoDetails(
    model=pinterest_board_model,
    prompt="Return the two main colors in this photo as a single HEX code",
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
    json_data=pinterest_hex_colors,
)

clothing_job = ExtractPhotoDetails(
    model=closet_clothing_model,
    prompt=(
        "Extract the main colors of the clothing item in this photo as HEX codes. "
        "Ignore the background, skin, hair, and any surroundings."
    ),
    tool={
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
    },
    json_data=closet_hex_colors,
)

# one model call for one photo; returns whatever the tool's schema promised
def extract_colors(path: Path, job: ExtractPhotoDetails) -> dict:
    response = client.messages.create(
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
            data[photo.name] = extract_colors(photo, job)["colors"]
            # save per photo so an interrupt doesn't throw away calls already paid for
            save_data(data, job.json_data)
            source = "new"

        print(f"{photo.name}: {', '.join(data[photo.name])} ({source})")

    return data


def run_color_palettes(folder: Path = pinterest_board_folder) -> dict:
    return run(folder, palette_job)


def run_closet_colors(folder: Path = closet_clothing_folder) -> dict:
    return run(folder, clothing_job)

def validate_hex_value(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"not a hex color: {value!r}")
    
    hex_value = regex_hex.match(value.strip())
    if not hex_value:
        raise ValueError(f"not a hex color: {value!r}")
    
    digits = hex_value.group(1)

    #fill in remainder of hex value to have correct amount of digits
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.upper()