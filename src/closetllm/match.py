"""Match closet garments to palette colors using the hex codes already on disk.

No model calls happen here. extract.py paid for those once and cached the
results; this reads the two JSON files and does arithmetic.
"""

from typing import Optional

from closetllm.color import (
    default_cutoff,
    matches_by_color,
    relationship,
)
from closetllm.config import pinterest_hex_colors, closet_hex_colors
from closetllm.extract import load_data


def run_matches(cutoff: float = default_cutoff, limit: Optional[int] = None) -> dict:
    """Print, for every palette color, the garments that come close to it."""
    palettes = load_data(pinterest_hex_colors)
    closet = load_data(closet_hex_colors)

    if not palettes:
        raise FileNotFoundError(f"no palettes saved yet — run `closetllm palettes` first")
    if not closet:
        raise FileNotFoundError(f"no clothes saved yet — run `closetllm clothes` first")

    results = {}

    for palette_name, palette_colors in sorted(palettes.items()):
        by_color = matches_by_color(palette_colors, closet, cutoff)
        results[palette_name] = by_color

        found = sum(len(hits) for hits in by_color.values())
        print(f"\n{palette_name}  {' '.join(palette_colors)}")

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
                how = relationship(palette_color, closet[name][0])
                print(f"  {palette_color}  {score:5.1f}  {name}  ({how})")

    return results