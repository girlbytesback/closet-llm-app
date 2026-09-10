from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from closetllm.color import default_cutoff
from closetllm.extract import load_data
from closetllm.match import build_matches, compute_matches
from closetllm.config import (
    color_palettes_folder,
    garment_hex_colors,
    garment_url_prefix,
    palette_hex_colors,
    palette_url_prefix,
    project_root,
    web_garment_folder,
)
from closetllm.schemas import GarmentsResponse, MatchesResponse, PalettesResponse

import json
import logging


log = logging.getLogger("closetllm")
app = FastAPI(title="closetLLM")

@app.get("/health")
def health():
    garments = load_data(garment_hex_colors)
    palettes = load_data(palette_hex_colors)
    return {
        "ok": bool(garments and palettes),
        "garments": len(garments),
        "palettes": len(palettes),
    }

@app.exception_handler(json.JSONDecodeError)
def corrupt_data(request: Request, exc: json.JSONDecodeError):
    log.error("corrupt data storage while serving %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "data storage is corrupt; re-run extraction"},
    )

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


# ── Static assets ──────────────────────────────────────────────────────────
# Everything below is registered AFTER the routes above on purpose: Starlette
# matches in registration order, and a mount swallows every path beneath it.
# A mount at "/" registered earlier would shadow every endpoint.
#
# The exists() guards matter because StaticFiles checks its directory when it
# is constructed — at import time. Without them, importing this module fails
# anywhere the folders are absent, which includes CI and the test suite.

# The mount paths come from config, not string literals: match.py builds every
# "src" in the matches document from those same two values, so a literal here
# that drifts from config serves 404s for photos the UI is already asking for.
#
# Garment photos are served from the web-sized copies, not the originals: the
# multi-MB originals stay local and only feed offline extraction.
if web_garment_folder.exists():
    app.mount(garment_url_prefix, StaticFiles(directory=web_garment_folder), name="garments")

if color_palettes_folder.exists():
    app.mount(palette_url_prefix, StaticFiles(directory=color_palettes_folder), name="palettes")

# The built React app. html=True serves index.html at "/", which is what makes
# this a single-origin deployment: one process answers HTML, images and JSON,
# so there is no CORS in production. Registered LAST because it is the catch-all.
ui_dist = project_root / "src/ui/dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
