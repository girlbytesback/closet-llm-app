"""Command line entry point: walk a folder of images and print what Claude found."""

import argparse
from pathlib import Path
from typing import Iterator

from closetllm.config import closet_clothing_folder, pinterest_board_folder, img_types
from closetllm.extract import run_closet_colors, run_color_palettes


def images_in(folder: Path) -> Iterator[Path]:
    """Yield the image files in folder, skipping anything we can't open."""
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() in img_types:
            yield path


def main() -> None:
    parser = argparse.ArgumentParser(prog="closetllm")
    commands = parser.add_subparsers(dest="command", required=True)

    clothes = commands.add_parser("clothes", help="extract colors from clothing photos")
    clothes.add_argument("folder", nargs="?", type=Path, default=closet_clothing_folder)
    clothes.set_defaults(run=run_closet_colors)

    palettes = commands.add_parser("palettes", help="extract colors from palette photos")
    palettes.add_argument("folder", nargs="?", type=Path, default=pinterest_board_folder)
    palettes.set_defaults(run=run_color_palettes)

    args = parser.parse_args()
    try:
        args.run(args.folder)
    except FileNotFoundError as err:
        # a missing photos folder is user error, not a bug — no traceback needed
        raise SystemExit(f"{parser.prog}: {err}")

if __name__ == "__main__":
    main()
