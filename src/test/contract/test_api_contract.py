"""The HTTP surface the React UI codes against.

Status codes, payload shapes and query-parameter names are the contract here.
Whether a particular garment matches is the matching layer's business and is
tested there — these tests only care about the envelope.
"""

import pytest

from closetllm.color import default_cutoff
from closetllm.extract import save_data

from conftest import NEAR_BLACK, SAGE, SAMPLE_GARMENTS, SAMPLE_PALETTES


# ----------------------------------------------------------------- /health

def test_health_is_always_200(client):
    # a liveness probe must not depend on any data being extracted yet
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# --------------------------------------------------------------- /garments

def test_garments_returns_a_count_and_a_mapping(client, seeded):
    body = client.get("/garments").json()

    assert body["count"] == len(SAMPLE_GARMENTS)
    assert body["garments"] == SAMPLE_GARMENTS


def test_the_count_always_matches_the_payload(client, seeded):
    body = client.get("/garments").json()
    assert body["count"] == len(body["garments"])


def test_each_garment_maps_to_a_list_of_hex_strings(client, seeded):
    for colors in client.get("/garments").json()["garments"].values():
        assert isinstance(colors, list) and colors
        assert all(c.startswith("#") and len(c) == 7 for c in colors)


def test_garments_is_404_before_anything_is_extracted(client):
    response = client.get("/garments")

    assert response.status_code == 404
    assert response.json() == {"detail": "no clothes saved yet"}


def test_an_empty_store_is_404_not_an_empty_list(client, data_paths):
    # the UI distinguishes "run the extractor first" from "you own no clothes"
    save_data({}, data_paths.garments)
    assert client.get("/garments").status_code == 404


# --------------------------------------------------------- /color-palettes

def test_palettes_returns_a_count_and_a_mapping(client, seeded):
    body = client.get("/color-palettes").json()

    assert body["count"] == len(SAMPLE_PALETTES)
    assert body["palettes"] == SAMPLE_PALETTES


def test_palettes_is_404_before_anything_is_extracted(client):
    response = client.get("/color-palettes")

    assert response.status_code == 404
    assert response.json() == {"detail": "no palettes saved yet"}


def test_the_two_stores_are_independent(client, data_paths):
    # garments saved, palettes not: one endpoint works, the other 404s
    save_data(SAMPLE_GARMENTS, data_paths.garments)

    assert client.get("/garments").status_code == 200
    assert client.get("/color-palettes").status_code == 404


# ---------------------------------------------------------- /color-matches

def test_matches_returns_the_three_top_level_sections(client, seeded):
    body = client.get("/color-matches").json()
    assert set(body) == {"meta", "garments", "palettes"}


def test_meta_reports_the_cutoff_and_both_counts(client, seeded):
    meta = client.get("/color-matches").json()["meta"]

    assert meta["cutoff"] == default_cutoff
    assert meta["garment_count"] == len(SAMPLE_GARMENTS)
    assert meta["palette_count"] == len(SAMPLE_PALETTES)


def test_the_threshold_query_parameter_reaches_meta(client, seeded):
    meta = client.get("/color-matches", params={"threshold": 3.5}).json()["meta"]
    assert meta["cutoff"] == 3.5


def test_the_threshold_actually_filters(client, seeded):
    loose = client.get("/color-matches", params={"threshold": 15}).json()
    tight = client.get("/color-matches", params={"threshold": 1}).json()

    def hits(body):
        return len(body["palettes"]["sage_palette.jpeg"]["matches"][SAGE])

    assert hits(loose) > hits(tight)


def test_a_non_numeric_threshold_is_a_422(client, seeded):
    response = client.get("/color-matches", params={"threshold": "close-ish"})
    assert response.status_code == 422


def test_matches_is_404_when_nothing_is_extracted(client):
    response = client.get("/color-matches")

    assert response.status_code == 404
    assert "no color palettes saved yet" in response.json()["detail"]


def test_matches_is_404_when_only_palettes_exist(client, data_paths):
    save_data(SAMPLE_PALETTES, data_paths.palettes)
    response = client.get("/color-matches")

    assert response.status_code == 404
    assert "no clothes saved yet" in response.json()["detail"]


def test_every_garment_entry_carries_colors_and_a_src(client, seeded):
    for entry in client.get("/color-matches").json()["garments"].values():
        assert set(entry) == {"colors", "src"}
        assert entry["src"].startswith("/clothes/")


def test_every_palette_entry_carries_colors_a_src_and_matches(client, seeded):
    for entry in client.get("/color-matches").json()["palettes"].values():
        assert set(entry) == {"colors", "src", "matches"}
        assert entry["src"].startswith("/color-palettes/")


def test_a_palette_has_one_match_list_per_colour(client, seeded):
    # the UI renders a column per swatch, so the keys have to line up exactly
    for entry in client.get("/color-matches").json()["palettes"].values():
        assert list(entry["matches"]) == entry["colors"]


def test_every_match_is_a_garment_name_and_a_score(client, seeded):
    body = client.get("/color-matches").json()

    for entry in body["palettes"].values():
        for hits in entry["matches"].values():
            for hit in hits:
                assert set(hit) == {"garment", "score"}
                assert hit["garment"] in body["garments"]
                assert isinstance(hit["score"], (int, float))


def test_a_neutral_palette_colour_returns_an_empty_list_not_a_missing_key(client, seeded):
    matches = client.get("/color-matches").json()["palettes"]["sage_palette.jpeg"]["matches"]

    assert NEAR_BLACK in matches
    assert matches[NEAR_BLACK] == []


def test_matches_are_sorted_closest_first(client, seeded):
    for entry in client.get("/color-matches").json()["palettes"].values():
        for hits in entry["matches"].values():
            scores = [h["score"] for h in hits]
            assert scores == sorted(scores)


def test_the_response_is_json_serialisable_as_sent(client, seeded):
    # FastAPI would have raised on encoding, but this pins the header the UI
    # branches on
    response = client.get("/color-matches")
    assert response.headers["content-type"].startswith("application/json")


# ------------------------------------------------------------ route surface

@pytest.mark.parametrize("path", ["/health", "/garments", "/color-palettes", "/color-matches"])
def test_the_documented_routes_exist(client, path):
    assert path in client.app.openapi()["paths"]


@pytest.mark.parametrize("path", ["/health", "/garments", "/color-palettes", "/color-matches"])
def test_the_routes_are_get_only(client, path, seeded):
    assert client.post(path).status_code == 405


def test_an_unknown_route_is_404(client):
    assert client.get("/shoes").status_code == 404
