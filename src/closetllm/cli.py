"""Command line entry point: walk a folder of images and print what Claude found."""

import argparse
from pathlib import Path

from closetllm.config import color_palettes_folder, garment_folder, palette_matches
from closetllm.extract import run_closet_colors, run_color_palettes
from closetllm.match import run_matches, default_cutoff


# each command takes the parsed args and pulls out what it needs — `match`
# has no folder, so a shared signature of (folder) no longer works
def clothes_cmd(args) -> None:
    run_closet_colors(args.folder)


def palettes_cmd(args) -> None:
    run_color_palettes(args.folder)


def match_cmd(args) -> None:
    run_matches(args.cutoff, args.limit, args.out)


def main() -> None:
    parser = argparse.ArgumentParser(prog="closetllm")
    commands = parser.add_subparsers(dest="command", required=True)

    clothes = commands.add_parser("clothes", help="extract colors from clothing photos")
    clothes.add_argument("folder", nargs="?", type=Path, default=garment_folder)
    clothes.set_defaults(run=clothes_cmd)

    palettes = commands.add_parser("palettes", help="extract colors from palette photos")
    palettes.add_argument("folder", nargs="?", type=Path, default=color_palettes_folder)
    palettes.set_defaults(run=palettes_cmd)

    matches = commands.add_parser("match", help="match closet garments to palette colors")
    matches.add_argument("--cutoff", type=float, default=default_cutoff, help="max distance to count as a match")
    matches.add_argument("--limit", type=int, default=None, help="max garments shown per color")
    # bare --out takes the default path, --out somewhere.json takes that one
    matches.add_argument(
        "--out",
        type=Path,
        nargs="?",
        const=palette_matches,
        default=None,
        help=f"also write the matches as JSON (bare flag writes {palette_matches.name})",
    )
    matches.set_defaults(run=match_cmd)

    args = parser.parse_args()
    try:
        args.run(args)
    except FileNotFoundError as err:
        # a missing photos folder is user error, not a bug — no traceback needed
        raise SystemExit(f"{parser.prog}: {err}")

if __name__ == "__main__":
    main()