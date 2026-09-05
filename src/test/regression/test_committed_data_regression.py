"""Invariants over the JSON that's committed to the repo.

data/clothes.json and data/colors.json are not test fixtures — they're paid-for
model output that the eval, the CLI and the UI all read. A malformed entry
there is a bug that no amount of code testing catches, so it's checked here
directly.
"""

import json
import re

import pytest

from closetllm.color import validate_hex_value
from closetllm.config import (
    color_palettes_folder,
    garment_folder,
    garment_hex_colors,
    img_types,
    palette_hex_colors,
    palette_matches,
)
from closetllm.extract import load_data

HEX = re.compile(r"^#[0-9A-F]{6}$")

STORES = [
    pytest.param(garment_hex_colors, id="clothes.json"),
    pytest.param(palette_hex_colors, id="colors.json"),
]


def photos_in(folder):
    return {p.name for p in folder.iterdir() if p.suffix.lower() in img_types}


@pytest.fixture(scope="module", params=STORES)
def store(request):
    data = load_data(request.param)
    if not data:
        pytest.skip(f"{request.param.name} is empty — nothing extracted yet")
    return data


# ------------------------------------------------------------- both stores

def test_every_entry_is_a_non_empty_list(store):
    # an empty list saves cleanly and then crashes score_garment's min()
    for name, colors in store.items():
        assert isinstance(colors, list), name
        assert colors, name


def test_every_colour_is_a_normalized_six_digit_hex(store):
    # extract.run runs everything through validate_hex_value; anything here
    # that isn't already normalized was written by an older version
    for name, colors in store.items():
        for value in colors:
            assert HEX.match(value), f"{name}: {value}"
            assert validate_hex_value(value) == value


def test_every_key_looks_like_a_photo_filename(store):
    from pathlib import Path

    for name in store:
        assert Path(name).suffix.lower() in img_types, name


def test_no_duplicate_colours_within_one_entry(store):
    for name, colors in store.items():
        assert len(set(colors)) == len(colors), name


# -------------------------------------------------------- store vs. folder

def test_every_garment_photo_has_been_extracted():
    missing = photos_in(garment_folder) - set(load_data(garment_hex_colors))
    assert not missing, f"run `closetllm clothes` — not yet extracted: {sorted(missing)}"


def test_every_palette_photo_has_been_extracted():
    missing = photos_in(color_palettes_folder) - set(load_data(palette_hex_colors))
    assert not missing, f"run `closetllm palettes` — not yet extracted: {sorted(missing)}"


def test_every_extracted_garment_still_has_its_photo():
    # extract.run only ever adds keys, so a renamed photo leaves its old entry
    # behind — that is how GARMENT_1.jpg outlived the rename to .jpeg
    stale = set(load_data(garment_hex_colors)) - photos_in(garment_folder)
    assert not stale, f"no photo on disk for: {sorted(stale)}"


def test_every_extracted_palette_still_has_its_photo():
    stale = set(load_data(palette_hex_colors)) - photos_in(color_palettes_folder)
    assert not stale, f"no photo on disk for: {sorted(stale)}"


# --------------------------------------------------------------- shape rules

def test_a_garment_carries_exactly_one_colour():
    # the garment tool asks for the single dominant colour; more than one means
    # the multi-colour work landed and this expectation needs updating
    for name, colors in load_data(garment_hex_colors).items():
        assert len(colors) == 1, f"{name}: {colors}"


def test_a_palette_carries_exactly_two_colours():
    # the palette prompt asks for two; a palette with one would render a single
    # swatch and silently halve the matches
    for name, colors in load_data(palette_hex_colors).items():
        assert len(colors) == 2, f"{name}: {colors}"


# ---------------------------------------------------- the UI's build input

@pytest.fixture(scope="module")
def matches():
    if not palette_matches.exists():
        pytest.skip("matches.json has not been generated")
    return json.loads(palette_matches.read_text())


def test_the_ui_file_has_the_three_sections(matches):
    assert set(matches) == {"meta", "garments", "palettes"}


def test_the_ui_file_has_no_dangling_garment_references(matches):
    # `data.garments[hit.garment]?.src` renders nothing if this breaks
    for name, palette in matches["palettes"].items():
        for hits in palette["matches"].values():
            for hit in hits:
                assert hit["garment"] in matches["garments"], f"{name}: {hit['garment']}"


def test_the_ui_file_has_a_match_list_for_every_swatch(matches):
    for name, palette in matches["palettes"].items():
        for color in palette["colors"]:
            assert color in palette["matches"], f"{name}: {color}"


def test_the_ui_file_counts_agree_with_its_own_contents(matches):
    assert matches["meta"]["garment_count"] == len(matches["garments"])
    assert matches["meta"]["palette_count"] == len(matches["palettes"])


def test_the_ui_file_scores_are_inside_its_own_cutoff(matches):
    cutoff = matches["meta"]["cutoff"]
    for palette in matches["palettes"].values():
        for hits in palette["matches"].values():
            assert all(hit["score"] <= cutoff for hit in hits)


def test_the_ui_file_matches_are_sorted_closest_first(matches):
    for palette in matches["palettes"].values():
        for hits in palette["matches"].values():
            scores = [hit["score"] for hit in hits]
            assert scores == sorted(scores)


def test_the_written_match_keys_are_the_palettes_colours(matches):
    # as a *set*, not a list: save_data writes with sort_keys=True, so the
    # matches keys come back alphabetical while colors keeps the palette's own
    # order. The UI looks matches up by key, so the reordering is harmless —
    # but any test comparing the two as lists will always fail on the file.
    for name, palette in matches["palettes"].items():
        assert set(palette["matches"]) == set(palette["colors"]), name


def test_the_api_document_and_the_written_file_differ_only_in_key_order(matches):
    # the file goes through json.dumps(sort_keys=True); the API response does
    # not. Same content, different key order — worth pinning so nobody
    # "fixes" one to match the other.
    for palette in matches["palettes"].values():
        assert list(palette["matches"]) == sorted(palette["colors"])


def test_the_ui_file_is_current_with_the_stores(matches):
    # matches.json is a build artifact; regenerate with `closetllm match --out`
    assert set(matches["garments"]) == set(load_data(garment_hex_colors))
    assert set(matches["palettes"]) == set(load_data(palette_hex_colors))


def test_no_two_entries_are_the_same_garment_under_different_extensions():
    # a rename leaves the old key behind, so the garment is scored twice and
    # shows up twice in the UI. Caught here because neither store nor folder
    # check finds it on its own.
    from collections import Counter
    from pathlib import Path

    stems = Counter(Path(name).stem for name in load_data(garment_hex_colors))
    duplicates = {stem: count for stem, count in stems.items() if count > 1}
    assert not duplicates, f"same garment under two extensions: {sorted(duplicates)}"
