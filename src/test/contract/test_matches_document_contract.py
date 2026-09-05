"""The matches.json document, checked against what the UI dereferences.

src/ui/src/PickYourCharacter.jsx reads, specifically:

    data.palettes[file].src
    data.palettes[file].colors           -> mapped to one group per swatch
    data.palettes[file].matches[hex]     -> [{garment, score}]
    data.garments[hit.garment].src

Anything that breaks one of those lines belongs in this file.
"""

import json

from closetllm.color import default_cutoff
from closetllm.config import garment_url_prefix, palette_url_prefix
from closetllm.match import build_matches, compute_matches

from conftest import SAGE


def document(seeded, cutoff=default_cutoff):
    return build_matches(compute_matches(cutoff), cutoff)


def test_the_document_survives_a_json_round_trip(seeded):
    # it is written to disk and imported by Vite, so every key and value has to
    # be a plain JSON type — a tuple or a Path would fail here
    doc = document(seeded)
    assert json.loads(json.dumps(doc)) == doc


def test_the_top_level_keys_are_exactly_the_three_the_ui_reads(seeded):
    assert set(document(seeded)) == {"meta", "garments", "palettes"}


def test_meta_carries_the_three_fields_it_promises(seeded):
    assert set(document(seeded)["meta"]) == {"cutoff", "garment_count", "palette_count"}


def test_every_palette_colour_has_a_matches_entry(seeded):
    # the UI does `palette.matches[hex] ?? []`; the fallback should never fire
    for palette in document(seeded)["palettes"].values():
        for hex_value in palette["colors"]:
            assert hex_value in palette["matches"]


def test_every_matched_garment_resolves_in_the_garments_map(seeded):
    # `data.garments[hit.garment]?.src` renders a broken image if this breaks
    doc = document(seeded)

    for palette in doc["palettes"].values():
        for hits in palette["matches"].values():
            for hit in hits:
                assert hit["garment"] in doc["garments"]


def test_image_urls_use_the_configured_prefixes(seeded):
    doc = document(seeded)

    assert all(g["src"].startswith(garment_url_prefix + "/") for g in doc["garments"].values())
    assert all(p["src"].startswith(palette_url_prefix + "/") for p in doc["palettes"].values())


def test_image_urls_are_url_safe(seeded):
    # public/ symlinks the photo folders, so the browser fetches these verbatim
    for entry in document(seeded)["garments"].values():
        assert " " not in entry["src"]


def test_scores_are_plain_numbers_the_ui_can_print(seeded):
    for palette in document(seeded)["palettes"].values():
        for hits in palette["matches"].values():
            for hit in hits:
                assert isinstance(hit["score"], (int, float))
                assert not isinstance(hit["score"], bool)


def test_colors_is_a_list_so_the_ui_can_map_over_it(seeded):
    # `palette.colors.map(...)` — a dict or a string would render nonsense
    for palette in document(seeded)["palettes"].values():
        assert isinstance(palette["colors"], list)


def test_the_swatch_order_is_the_palettes_own_order(seeded):
    # the two swatches are shown side by side in the order the model returned
    assert document(seeded)["palettes"]["sage_palette.jpeg"]["colors"][0] == SAGE


def test_a_cutoff_that_matches_nothing_still_produces_a_renderable_document(seeded):
    doc = document(seeded, cutoff=0.0)

    assert doc["garments"]                        # the closet still renders
    assert set(doc["palettes"]) == {"sage_palette.jpeg", "pink_palette.jpeg"}
    for palette in doc["palettes"].values():
        assert all(hits == [] for hits in palette["matches"].values())


def test_the_api_and_the_written_file_are_the_same_document(seeded, client):
    # the UI can read either; they must not drift apart
    assert client.get("/color-matches").json() == json.loads(json.dumps(document(seeded)))
