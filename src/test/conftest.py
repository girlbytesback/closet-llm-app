"""Shared fixtures.

Two things every test outside the pure-math ones needs: somewhere to put JSON
that isn't the real data/ directory, and a stand-in for the model so no test
ever spends money or needs a key.

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

from closetllm import api, extract, match
from helpers import FakeMessages, FakeResponse, FakeBlock, read_json  # noqa: F401

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
    garments = tmp_path / "data" / "clothes.json"
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


@pytest.fixture
def client(data_paths):
    from fastapi.testclient import TestClient

    return TestClient(api.app)


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
