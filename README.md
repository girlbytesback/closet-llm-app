#  `closetLLM` documentation 👗🎨
❗❗ IN PROGRESS, continuously updating and currently adding full fledged API documentation.. ❗❗

## 🌀 About the Project:

Matches garments from my closet against color palettes manually uploaded from Pinterest.

LLM model (Claude Vision Language Model) reads the dominant colors out of each garment photo and returns the clothing items that match color palette, using mathematics + color/computer vision calculations

**The interesting part is the eval.** I hand-measured a 48-garment
answer key and scored the model against it: only 9/48 extractions land
within ΔE ≤ 5 (32/48 within ΔE ≤ 10), and the misses aren't random —
the model reads colors lighter (+7.3 L*) and more saturated (+5.3
chroma) than reality, worst on dark saturated reds.


FULL EVAL REPORT: [eval report](src/evals/README.md).

## How it works:

garment + palette photos → `extract` (Claude vision → hex) →
`match` (CIEDE2000 distance, cutoff-filtered) → JSON → React UI

## Run it

```bash
uv sync
export ANTHROPIC_API_KEY=your-key

uv run closetllm clothes     # extract colors from garment photos
uv run closetllm palettes    # extract colors from palette photos
uv run closetllm match       # score the closet against palettes
uv run pytest src/test       # unit tests
```

UI: `cd src/ui && npm install && npm run dev`

## Status/To Be Implemented:

Currently working through matching clothing pieces with multiple colors to palette, and migrating CLI to API endpoints + deploy. 

Scope will expand beyond colors and match entire garments to a photo (articles of clothing vs clothing color)