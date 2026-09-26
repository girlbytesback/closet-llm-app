from fastapi import (
    FastAPI, 
    HTTPException, 
    Query, 
    Request, 
    File, 
    UploadFile, 
    Response,
    Depends
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from closetllm.color import default_cutoff, max_cutoff
from closetllm.extract import load_data, palette_job, garment_job
from closetllm.match import build_matches, compute_matches
from closetllm.config import (
    garment_hex_colors,
    palette_hex_colors,
    project_root,
)
from closetllm.schemas import (
    GarmentsResponse,
    PalettesResponse,
    StatsResponse,
    UploadResponse,
    SessionRequest
)
from closetllm.auth import current_user, verify, COOKIE
from closetllm.ingest import ingest
from closetllm import db, storage

import json
import logging
import time


log = logging.getLogger("closetllm")
app = FastAPI(title="closetLLM")

@app.get("/health")
def health():
    # A liveness probe, so it deliberately touches no data: it stays 200 before
    # anything is extracted and while the JSON on disk is corrupt. Whether the
    # store has usable content is what /garments and /color-palettes report.
    return {"ok": True}

# Auth as a route dependency rather than a handler argument, for the handlers
# that only need the 401 current_user raises and never read the user id. The
# read routes below still serve the JSON store, which has no owner column, so
# they are in that group; the two upload routes take the id as an argument
# because the row they write is owned.
auth_required = [Depends(current_user)]

# NEW SESSION

@app.post("/session")
def create_session(body: SessionRequest, response: Response):
    claims = verify(body.access_token)           # 401 "bad token" if it's not a real supabase jwt
    response.set_cookie(
        key=COOKIE,
        value=body.access_token,
        httponly=True,        # javascript can't read it
        secure=True,          # https only (chrome allows it on localhost too)
        samesite="lax",       # other sites can't POST with it
        max_age=max(0, int(claims["exp"] - time.time())),   # dies when the jwt does
        path="/",
    )
    return {"ok": True}

@app.delete("/session")
def delete_session(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}

@app.get("/stats", response_model=StatsResponse, dependencies=auth_required)
def stats():
    # Readiness, not liveness: how much is actually in the store. Unlike
    # /garments an empty store is 200 with zeroes rather than a 404, because
    # "you have extracted nothing" is the answer here, not a missing resource.
    garments = load_data(garment_hex_colors)
    palettes = load_data(palette_hex_colors)
    return {
        "ok": bool(garments and palettes),
        "garments": len(garments),
        "palettes": len(palettes),
    }

@app.get("/garments", response_model=GarmentsResponse)
def get_garments(user_id: str = Depends(current_user)):
    garments = db.load_user_colors(db.garments, user_id)
    if not garments:
        raise HTTPException(status_code=404, detail="no clothes saved yet")
    return {"count": len(garments), "garments": garments}

@app.get("/color-palettes", response_model=PalettesResponse, dependencies=auth_required)
def get_color_palettes(user_id: str = Depends(current_user)):
    palettes = db.load_user_colors(db.palettes, user_id)
    if not palettes:
        raise HTTPException(status_code=404, detail="no palettes saved yet")
    return {"count": len(palettes), "palettes": palettes}

@app.get("/color-matches")
def color_matches(
    cutoff: float = Query(default_cutoff, ge=0, le=max_cutoff),
    user_id: str = Depends(current_user),
) -> dict:
    # 1. load this user's colors from the db
    garments = db.load_user_colors(db.garments, user_id)
    palettes = db.load_user_colors(db.palettes, user_id)

    # 2. the color math (pure; doesn't know about db or storage). An empty
    #    store is a 404 like /garments, not a 500 — "extract something first"
    #    is a state the UI renders, not a bug.
    try:
        results = compute_matches(garments, palettes, cutoff)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err))
    doc = build_matches(garments, results, cutoff)

    # 3. swap in photo links from the bucket
    garment_keys = db.load_user_keys(db.garments, user_id)     # {filename: key}
    palette_keys = db.load_user_keys(db.palettes, user_id)
    links = storage.signed_urls(list(garment_keys.values()) + list(palette_keys.values()))

    for name, garment in doc["garments"].items():
        garment["src"] = links.get(garment_keys.get(name))
    for name, palette in doc["palettes"].items():
        palette["src"] = links.get(palette_keys.get(name))

    return doc

@app.post("/upload-garments", status_code=201, response_model=UploadResponse)
def upload_garment(file: UploadFile = File(), user_id: str = Depends(current_user)):
    return ingest(file, garment_job, db.garments, user_id, needs_web_copy=True)


@app.post("/upload-palettes", status_code=201, response_model=UploadResponse)
def upload_palette(file: UploadFile = File(), user_id: str = Depends(current_user)):
    return ingest(file, palette_job, db.palettes, user_id, needs_web_copy=False)

@app.exception_handler(json.JSONDecodeError)
def corrupt_data(request: Request, exc: json.JSONDecodeError):
    log.error("corrupt data storage while serving %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "data storage is corrupt; re-run extraction"},
    )


# ── Static assets ─────────────────────────────────────────────────────────
# Photos are not served from this process any more: they live in the storage
# bucket, and /color-matches hands the UI a signed link per photo. The React
# app is the only thing left to mount.
#
# It is registered AFTER the routes above on purpose: Starlette matches in
# registration order, and a mount swallows every path beneath it — a mount at
# "/" registered earlier would shadow every endpoint.
#
# The exists() guard matters because StaticFiles checks its directory when it
# is constructed, at import time. Without it, importing this module fails
# anywhere dist/ is absent, which includes CI and the test suite.
#
# html=True serves index.html at "/", which is what makes this a single-origin
# deployment: one process answers both the HTML and the JSON, so there is no
# CORS in production.
@app.middleware("http")
async def cache_policy(request: Request, call_next):
    response = await call_next(request)
    ctype = response.headers.get("content-type", "")

    if ctype.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    elif request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    return response

ui_dist = project_root / "src/ui/dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="ui")
