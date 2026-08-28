"""Scoring the closet against the palettes, and the three things we do with it.

compute_matches is the only part that thinks. filter/print/write are consumers
that each take the scores and do one thing, so a web server can later import
compute_matches without dragging the printing along with it.
"""

from pathlib import Path
from typing import Optional
from urllib.parse import quote

from closetllm.color import (
    default_cutoff,
    matches_for_color_palette
)
from closetllm.config import (
    palette_hex_colors,
    garment_hex_colors,
    garment_url_prefix,
    palette_url_prefix,
)
from closetllm.extract import load_data, save_data

def compute_matches(threshold: float = default_cutoff) -> dict:
    color_palettes = load_data(palette_hex_colors)
    garments = load_data(garment_hex_colors)

    if not color_palettes:
        raise FileNotFoundError("no color palettes saved yet")
    if not garments:
        raise FileNotFoundError("no clothes saved yet")
    return {
        name: matches_for_color_palette(palette_colors, garments, threshold)
        for name, palette_colors in sorted(color_palettes.items())
    }

def build_matches(results: dict, cutoff: float) -> dict:
    #shape the scores into the document the web UI reads.
    garments = load_data(garment_hex_colors)
    return {
        "meta": {
            "cutoff": cutoff,
            "garment_count": len(garments),
            "palette_count": len(results),
        },
        "garments": {
            name: {
                "colors": colors,
                # quoted so any spaces or odd characters in a filename survive the URL
                "src": f"{garment_url_prefix}/{quote(name)}",
            }
            for name, colors in sorted(garments.items())
        },
        "palettes": {
            name: {
                # the inner keys already are the palette's colors, in order
                "colors": list(by_color),
                "src": f"{palette_url_prefix}/{quote(name)}",
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

def write_matches(results: dict, path: Path, cutoff: float) -> None:
    save_data(build_matches(results, cutoff), path)

def print_matches(results: dict, threshold: float, limit: Optional[int] = None) -> None:
    # compute_matches already returns {palette: {palette_color: [(garment, score)]}},
    # so printing is a walk over that — no second pass over the garments
    for palette_name, by_color in sorted(results.items()):
        found = sum(len(hits) for hits in by_color.values())
        print(f"\n{palette_name}  {' '.join(by_color)}")

        if not found:
            print(f"  nothing under {threshold:g}")
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
    threshold: float = default_cutoff,
    limit: Optional[int] = None,
    out: Optional[Path] = None,
) -> dict:
    # the printout and the exported file are the same set of matches, both cut
    # at the same threshold — what you read in the terminal is what the UI gets
    results = compute_matches(threshold)

    print_matches(results, threshold, limit)

    if out is not None:
        write_matches(results, out, threshold)
        print(f"\nwrote {out}")

    return results
