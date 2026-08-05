"""Command line entry point: walk a folder of images and print what Claude found."""

import argparse
from pathlib import Path

from closetllm.config import closet_clothing_folder, pinterest_board_folder
from closetllm.extract import run_closet_colors, run_color_palettes
from closetllm.match import run_matches


# each command takes the parsed args and pulls out what it needs — `match`
# has no folder, so a shared signature of (folder) no longer works
def clothes_cmd(args) -> None:
    run_closet_colors(args.folder)


def palettes_cmd(args) -> None:
    run_color_palettes(args.folder)


def match_cmd(args) -> None:
    run_matches(args.cutoff, args.limit)


def main() -> None:
    parser = argparse.ArgumentParser(prog="closetllm")
    commands = parser.add_subparsers(dest="command", required=True)

    clothes = commands.add_parser("clothes", help="extract colors from clothing photos")
    clothes.add_argument("folder", nargs="?", type=Path, default=closet_clothing_folder)
    clothes.set_defaults(run=clothes_cmd)

    palettes = commands.add_parser("palettes", help="extract colors from palette photos")
    palettes.add_argument("folder", nargs="?", type=Path, default=pinterest_board_folder)
    palettes.set_defaults(run=palettes_cmd)

    matches = commands.add_parser("match", help="match closet garments to palette colors")
    matches.add_argument("--cutoff", type=float, default=25.0, help="max distance to count as a match")
    matches.add_argument("--limit", type=int, default=None, help="max garments shown per color")
    matches.set_defaults(run=match_cmd)

    args = parser.parse_args()
    try:
        args.run(args)
    except FileNotFoundError as err:
        # a missing photos folder is user error, not a bug — no traceback needed
        raise SystemExit(f"{parser.prog}: {err}")

if __name__ == "__main__":
    main()