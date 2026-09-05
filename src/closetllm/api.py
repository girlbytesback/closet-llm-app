from fastapi import FastAPI, HTTPException
from closetllm.color import default_cutoff
from closetllm.extract import load_data
from closetllm.match import build_matches, compute_matches
from closetllm.config import garment_hex_colors, palette_hex_colors

app = FastAPI(title="closetLLM")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/garments")
def get_garments():
    garments = load_data(garment_hex_colors)
    if not garments:
        raise HTTPException(status_code=404, detail="no clothes saved yet")
    return {"count": len(garments), "garments": garments}

@app.get("/color-palettes")
def get_color_palettes():
    palettes = load_data(palette_hex_colors)
    if not palettes:
            raise HTTPException(status_code=404, detail="no palettes saved yet")
    return {"count": len(palettes), "palettes": palettes}

@app.get("/color-matches")
def get_color_matches(threshold: float = default_cutoff):
    try:
        data = compute_matches(threshold)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return build_matches(data, threshold)