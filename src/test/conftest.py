"""Shared fixtures.

Three things every test outside the pure-math ones needs: somewhere to put
JSON that isn't the real data/ directory, a stand-in for the model so no test
ever spends money or needs a key, and a stand-in for the database so no test
ever reaches the one the real closet lives in.

config.py hands out its paths as module-level constants, and match.py and
api.py bind them by name at import. Patching closetllm.config.<name> after
that would be patching a copy nobody reads — so the fixtures below patch the
names where they are actually looked up.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# so `from helpers import ...` works from any test subdirectory
sys.path.insert(0, str(Path(__file__).parent))

from closetllm import api, db, extract, match, storage
from closetllm.auth import current_user
from helpers import (  # noqa: F401
    FakeDB,
    FakeStorage,
    FakeMessages,
    FakeResponse,
    FakeBlock,
    RefusingEngine,
    TEST_USER,
    jpeg_bytes,
    read_json,
)

# One chromatic palette color with two plausible garments, one near-black to
# exercise the neutral filter, and one filename with a space in it.
SAGE = "#B5C29A"
NEAR_SAGE = "#B7C39B"      # 0.45 from SAGE — inside any sane cutoff
OLIVE = "#A9B98C"          # 3.09 from SAGE — still a match, but second
PINK = "#E4A8C0"
NEAR_PINK = "#DFA3BC"      # 1.36 from PINK
NEAR_BLACK = "#1E1E20"     # chroma below neutral_chroma

SAMPLE_PALETTES = {
    "sage_palette.jpeg": [SAGE, NEAR_BLACK],
    "pink_palette.jpeg": [PINK],
}

SAMPLE_GARMENTS = {
    "sage_shirt.jpeg": [NEAR_SAGE],
    "olive_pants.jpeg": [OLIVE],
    "pink dress.jpeg": [NEAR_PINK],
    "black_coat.jpeg": [NEAR_BLACK],
}


@pytest.fixture
def data_paths(tmp_path, monkeypatch):
    """Redirect the two JSON stores at every module that reads them.

    Returns the paths so a test can seed or inspect them directly. Nothing is
    written here — an unseeded store is the "nothing extracted yet" case, which
    several tests depend on.
    """
    garments = tmp_path / "data" / "garments.json"
    palettes = tmp_path / "data" / "colors.json"

    for module in (match, api):
        monkeypatch.setattr(module, "garment_hex_colors", garments, raising=True)
        monkeypatch.setattr(module, "palette_hex_colors", palettes, raising=True)

    return SimpleNamespace(garments=garments, palettes=palettes, root=tmp_path)


@pytest.fixture
def seeded(data_paths):
    """data_paths, with the sample closet and palettes already on disk."""
    extract.save_data(SAMPLE_GARMENTS, data_paths.garments)
    extract.save_data(SAMPLE_PALETTES, data_paths.palettes)
    return data_paths


@pytest.fixture(autouse=True)
def no_real_database(request, monkeypatch):
    """Make an unfaked database call fail instead of reaching Supabase.

    db.engine is built at import from DATABASE_URL — on a laptop that is the
    database holding the real closet, and .env means it is always set. Every
    test therefore runs with the engine replaced by one that refuses; fake_db
    below patches the two functions that would have used it. The opt-in
    postgres tests are the only ones that keep a working engine.
    """
    if request.node.get_closest_marker("postgres"):
        return
    monkeypatch.setattr(db, "engine", RefusingEngine())


@pytest.fixture
def fake_db(monkeypatch):
    """Swap closetllm.db's two functions for the in-memory FakeDB.

    Same trick as fake_model, and for the same reason: the tests that use it
    care about what ingest does with a row, not about Postgres. ingest calls
    both functions through the module (`db.add_photo`), so patching the
    attributes here redirects every caller.
    """
    fake = FakeDB()
    monkeypatch.setattr(db, "add_photo", fake.add_photo)
    monkeypatch.setattr(db, "load_user_colors", fake.load_user_colors)
    return fake


@pytest.fixture
def fake_storage(monkeypatch):
    """Swap the three storage functions for an in-memory bucket.

    Same trick as fake_model and fake_db, and for the same reason: the real
    ones talk to Supabase, so without this an upload test would put a photo in
    the bucket the actual closet lives in. Every caller goes through the module
    (`storage.put`), so patching the attributes here redirects all of them.
    """
    fake = FakeStorage()
    monkeypatch.setattr(storage, "put", fake.put)
    monkeypatch.setattr(storage, "delete", fake.delete)
    monkeypatch.setattr(storage, "signed_urls", fake.signed_urls)
    return fake


@pytest.fixture
def client(data_paths):
    """A signed-in client, so no test needs a real Supabase token.

    dependency_overrides swaps the Depends target for the lifetime of the
    fixture; the clear() after the yield puts the real dependency back, which is
    what the auth tests rely on to exercise it.
    """
    from fastapi.testclient import TestClient

    api.app.dependency_overrides[current_user] = lambda: TEST_USER
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


@pytest.fixture
def fake_model(monkeypatch):
    """Install a scripted stand-in for the Anthropic client.

    Call it with the tool inputs you want back, in order:
        messages = fake_model({"color": "#B5C29A", "item": "shirt"})
    """

    def install(*tool_inputs, stop_reason="tool_use"):
        replies = [
            r
            if isinstance(r, (FakeResponse, Exception))
            else FakeResponse([FakeBlock("tool_use", r)], stop_reason)
            for r in tool_inputs
        ]
        messages = FakeMessages(replies)
        monkeypatch.setattr(extract, "_client", SimpleNamespace(messages=messages))
        return messages

    return install


@pytest.fixture
def photo_folder(tmp_path):
    """Make a folder of real (tiny, solid-color) JPEGs.

    Real files rather than touch()ed empty ones, because image_block actually
    opens them.
    """
    from PIL import Image

    folder = tmp_path / "photos"
    folder.mkdir()

    def add(name, color=(180, 194, 154), size=(40, 40)):
        path = folder / name
        if path.suffix.lower() == ".png":
            Image.new("RGB", size, color).save(path, format="PNG")
        else:
            Image.new("RGB", size, color).save(path, format="JPEG")
        return path

    return SimpleNamespace(path=folder, add=add)


@pytest.fixture
def jobs_in_tmp(data_paths, monkeypatch):
    """Point the two extraction jobs at the throwaway stores.

    run_closet_colors/run_color_palettes read these module globals at call
    time, so replacing them here redirects the whole CLI path.
    """
    import dataclasses

    monkeypatch.setattr(
        extract,
        "garment_job",
        dataclasses.replace(extract.garment_job, json_data=data_paths.garments),
    )
    monkeypatch.setattr(
        extract,
        "palette_job",
        dataclasses.replace(extract.palette_job, json_data=data_paths.palettes),
    )
    return data_paths


@pytest.fixture
def upload_paths(data_paths, fake_db, fake_storage):
    """Redirect everything an upload touches away from the real thing.

    Two halves, because an upload writes to two places: a row and a photo. No
    folders to redirect any more — ingest stages the photo in a temp directory
    and uploads it, so the only things to fake are the database and the bucket.
    Both are returned, as `.db` and `.storage`, which is where these tests
    assert.
    """
    return SimpleNamespace(db=fake_db, storage=fake_storage)
