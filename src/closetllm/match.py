from typing import Optional

from closetllm.color import (
    default_cutoff,
    matches_for_color_palette
)
from closetllm.config import pinterest_hex_colors, closet_hex_colors
from closetllm.extract import load_data

def compute_matches(threshold: float = default_cutoff) -> dict:
    color_palettes = load_data(pinterest_hex_colors)
    garments = load_data(closet_hex_colors)

    if not color_palettes:
        raise FileNotFoundError("no color palettes saved yet")
    if not garments:
        raise FileNotFoundError("no clothes saved yet")
    return {
        name: matches_for_color_palette(color_palettes, garments, threshold)
        for name, color_palettes in sorted(color_palettes.items())
    }

def run_matches(threshold: float = default_cutoff, limit: Optional[int] = None) -> dict:
    # for every palette color in each palette pair, match hex colors based on threshold
    results = compute_matches(threshold)

    for palette_name, palette_colors in sorted(results.items()):
        by_color = matches_for_color_palette(palette_colors, closet, threshold)
        results[palette_name] = by_color

        found = sum(len(hits) for hits in by_color.values())
        print(f"\n{palette_name}  {' '.join(palette_colors)}")

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