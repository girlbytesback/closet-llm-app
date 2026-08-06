from typing import Optional

from closetllm.color import (
    default_cutoff,
    matches_by_color
)
from closetllm.config import pinterest_hex_colors, closet_hex_colors
from closetllm.extract import load_data

def run_matches(threshold: float = default_cutoff, limit: Optional[int] = None) -> dict:
    # for every palette color in each palette pair, match hex colors based on threshold
    palettes = load_data(pinterest_hex_colors)
    closet = load_data(closet_hex_colors)

    if not palettes:
        raise FileNotFoundError(f"no color palettes saved yet")
    if not closet:
        raise FileNotFoundError(f"no clothes saved yet")

    results = {}

    for palette_name, palette_colors in sorted(palettes.items()):
        by_color = matches_by_color(palette_colors, closet, threshold)
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