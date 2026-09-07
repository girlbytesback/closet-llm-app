from fastapi import FastAPI, HTTPException, Query
from closetllm.color import default_cutoff
from closetllm.extract import load_data
from closetllm.match import build_matches, compute_matches
from closetllm.config import garment_hex_colors, palette_hex_colors
from closetllm.schemas import GarmentsResponse, MatchesResponse, PalettesResponse

app = FastAPI(title="closetLLM")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/garments", response_model=GarmentsResponse)
def get_garments():
    garments = load_data(garment_hex_colors)
    if not garments:
        raise HTTPException(status_code=404, detail="no clothes saved yet")
    return {"count": len(garments), "garments": garments}

@app.get("/color-palettes", response_model=PalettesResponse)
def get_color_palettes():
    palettes = load_data(palette_hex_colors)
    if not palettes:
        raise HTTPException(status_code=404, detail="no palettes saved yet")
    return {"count": len(palettes), "palettes": palettes}

@app.get("/color-matches", response_model=MatchesResponse)
def get_color_matches(
    cutoff: float = Query(
        default_cutoff,
        ge=0,
        le=100,
        description="Maximum ΔE (CIEDE2000) for a garment to count as a match.",
    ),
):
    try:
        data = compute_matches(cutoff)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return build_matches(data, cutoff)
    