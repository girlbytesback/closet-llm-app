from typing import Optional

from closetllm.color import (
    default_cutoff,
    matches_for_color_palette
)
from closetllm.config import palette_hex_colors, garment_hex_colors
from closetllm.extract import load_data

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

def run_matches(threshold: float = default_cutoff, limit: Optional[int] = None) -> dict:
    # for every palette color in each palette pair, match hex colors based on threshold
    results = compute_matches(threshold)

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

    return results