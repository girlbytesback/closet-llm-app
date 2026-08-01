"""Command line entry point: walk a folder of images and print what Claude found."""

import argparse
from pathlib import Path
from typing import Iterator

from closetllm.config import clothes_folder, color_palettes_folder, img_types
from closetllm.extract import extract_clothing_colors, run_color_palettes


def images_in(folder: Path) -> Iterator[Path]:
    """Yield the image files in folder, skipping anything we can't open."""
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() in img_types:
            yield path


def run_clothes(folder: Path) -> None:
    for photo in images_in(folder):
        result = extract_clothing_colors(photo)
        print(f"{photo.name}: {result['item']} -> {', '.join(result['colors'])}")


def run_palettes(folder: Path) -> None:
    run_color_palettes(folder)


def main() -> None:
    parser = argparse.ArgumentParser(prog="closetllm")
    commands = parser.add_subparsers(dest="command", required=True)

    clothes = commands.add_parser("clothes", help="extract colors from clothing photos")
    clothes.add_argument("folder", nargs="?", type=Path, default=clothes_folder)
    clothes.set_defaults(run=run_clothes)

    palettes = commands.add_parser("palettes", help="extract colors from palette photos")
    palettes.add_argument("folder", nargs="?", type=Path, default=color_palettes_folder)
    palettes.set_defaults(run=run_palettes)

    args = parser.parse_args()
    args.run(args.folder)


if __name__ == "__main__":
    main()
