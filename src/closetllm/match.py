"""Scoring the closet against the palettes, and the three things we do with it.

compute_matches is the only part that thinks, and it thinks about nothing but
the two dicts it is handed: the caller decides whether those came out of
Postgres (api.py) or off disk (run_matches, for the CLI). filter/print/write
are consumers that each take the scores and do one thing.
"""

from pathlib import Path
from typing import Optional

from closetllm.color import (
    default_cutoff,
    matches_for_color_palette
)
from closetllm.config import (
    palette_hex_colors,
    garment_hex_colors,
)
from closetllm.extract import load_data, save_data

def compute_matches(garments: dict, palettes: dict, cutoff: float = default_cutoff) -> dict:
    # an empty side is a valid input: no palettes gives {}, no garments gives
    # every swatch an empty hit list. The API draws both; only the CLI
    # (run_matches) still treats them as errors.
    return {
        name: matches_for_color_palette(palette_colors, garments, cutoff)
        for name, palette_colors in sorted(palettes.items())
    }

def build_matches(garments: dict, results: dict, cutoff: float) -> dict:
    #shape + return the scores into doc the web UI reads
    return {
        "meta": {
            "cutoff": cutoff,
            "garment_count": len(garments),
            "palette_count": len(results),
        },
        # No "src" here: this function is the colour maths, and it has no way to
        # know where a photo lives. api.py fills the key in from the signed
        # bucket links before the document goes out.
        "garments": {
            name: {"colors": colors}
            for name, colors in sorted(garments.items())
        },
        "palettes": {
            name: {
                # the inner keys already are the palette's colors, in order
                "colors": list(by_color),
                "matches": {
                    color: [
                        # full float precision is noise on a number whose useful
                        # range is 0-30, and it triples the file size
                        {"garment": garment, "score": round(score, 2)}
                        for garment, score in hits
                    ]
                    for color, hits in by_color.items()
                },
            }
            for name, by_color in sorted(results.items())
        },
    }

def write_matches(garments: dict, results: dict, path: Path, cutoff: float) -> None:
    save_data(build_matches(garments, results, cutoff), path)

def print_matches(results: dict, cutoff: float, limit: Optional[int] = None) -> None:
    # compute_matches already returns {palette: {palette_color: [(garment, score)]}},
    # so printing is a walk over that — no second pass over the garments
    for palette_name, by_color in sorted(results.items()):
        found = sum(len(hits) for hits in by_color.values())
        print(f"\n{palette_name}  {' '.join(by_color)}")

        if not found:
            print(f"  nothing under {cutoff:g}")
            continue

        # one block per palette color — a palette is two separate questions,
        # so the answers stay separate rather than being merged into one score
        for palette_color, hits in by_color.items():
            if not hits:
                print(f"  {palette_color}  —")
                continue
            for name, score in hits[:limit]:
                print(f"  {palette_color}  {score:5.1f}  {name}  ")

def run_matches(
    cutoff: float = default_cutoff,
    limit: Optional[int] = None,
    out: Optional[Path] = None,
) -> dict:
    # the CLI half: the closet it scores is the JSON `closetllm clothes` wrote,
    # not anybody's rows. The API reads the same functions off the database.
    garments = load_data(garment_hex_colors)
    palettes = load_data(palette_hex_colors)

    # check if empty occurs before running compute()
    if not palettes:
        raise FileNotFoundError("no color palettes saved yet")
    if not garments:
        raise FileNotFoundError("no clothes saved yet")

    # the printout and the exported file are the same set of matches, both cut
    # at the same cutoff — what you read in the terminal is what the UI gets
    results = compute_matches(garments, palettes, cutoff)

    print_matches(results, cutoff, limit)

    if out is not None:
        write_matches(garments, results, out, cutoff)
        print(f"\nwrote {out}")

    return results
