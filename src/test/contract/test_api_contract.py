"""The HTTP surface the React UI codes against.

Status codes, payload shapes and query-parameter names are the contract here.
Whether a particular garment matches is the matching layer's business and is
tested there — these tests only care about the envelope.
"""

import pytest

from closetllm import db
from closetllm.color import default_cutoff, max_cutoff
from closetllm.extract import save_data

from conftest import NEAR_BLACK, SAGE, SAMPLE_GARMENTS, SAMPLE_PALETTES
from helpers import TEST_USER


# ----------------------------------------------------------------- /health

def test_health_is_always_200(client):
    # a liveness probe must not depend on any data being extracted yet
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ------------------------------------------------------------------ /stats

def test_stats_counts_what_is_in_the_store(client, seeded):
    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "garments": len(SAMPLE_GARMENTS),
        "palettes": len(SAMPLE_PALETTES),
    }


def test_stats_is_200_with_zeroes_before_anything_is_extracted(client):
    # unlike /garments, an empty store is the answer here rather than a 404
    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"ok": False, "garments": 0, "palettes": 0}


def test_stats_is_not_ok_when_only_one_store_is_populated(client, data_paths):
    # nothing can be matched until both halves exist
    save_data(SAMPLE_GARMENTS, data_paths.garments)
    body = client.get("/stats").json()

    assert body == {"ok": False, "garments": len(SAMPLE_GARMENTS), "palettes": 0}


def test_stats_reports_corruption_like_the_other_data_routes(client, data_paths):
    write_corrupt(data_paths.garments)
    response = client.get("/stats")

    assert response.status_code == 500
    assert response.json() == {"detail": CORRUPT_DETAIL}


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


def test_an_empty_store_is_404_not_an_empty_list(client, fake_db):
    # the UI distinguishes "run the extractor first" from "you own no clothes"
    fake_db.seed(db.garments, TEST_USER, {})
    assert client.get("/garments").status_code == 404


def test_garments_only_returns_the_asking_users_rows(client, fake_db):
    # rows are owned; the id comes off the token, never off the query string
    fake_db.seed(db.garments, TEST_USER, {"mine.jpeg": [SAGE]})
    fake_db.seed(db.garments, "someone-else", {"theirs.jpeg": [NEAR_BLACK]})

    assert client.get("/garments").json()["garments"] == {"mine.jpeg": [SAGE]}


# --------------------------------------------------------- /color-palettes

def test_palettes_returns_a_count_and_a_mapping(client, seeded):
    body = client.get("/color-palettes").json()

    assert body["count"] == len(SAMPLE_PALETTES)
    assert body["palettes"] == SAMPLE_PALETTES


def test_palettes_is_404_before_anything_is_extracted(client):
    response = client.get("/color-palettes")

    assert response.status_code == 404
    assert response.json() == {"detail": "no palettes saved yet"}


def test_the_two_stores_are_independent(client, fake_db):
    # garments saved, palettes not: one endpoint works, the other 404s
    fake_db.seed(db.garments, TEST_USER, SAMPLE_GARMENTS)

    assert client.get("/garments").status_code == 200
    assert client.get("/color-palettes").status_code == 404


def test_the_palette_route_reads_the_palette_table(client, fake_db):
    # it read db.garments for a while, which served the closet back as
    # inspiration and made /color-palettes agree with /garments exactly
    fake_db.seed(db.garments, TEST_USER, SAMPLE_GARMENTS)
    fake_db.seed(db.palettes, TEST_USER, SAMPLE_PALETTES)

    assert client.get("/color-palettes").json()["palettes"] == SAMPLE_PALETTES


# ---------------------------------------------------------- /color-matches

def test_matches_returns_the_three_top_level_sections(client, seeded):
    body = client.get("/color-matches").json()
    assert set(body) == {"meta", "garments", "palettes"}


def test_meta_reports_the_cutoff_and_both_counts(client, seeded):
    meta = client.get("/color-matches").json()["meta"]

    assert meta["cutoff"] == default_cutoff
    assert meta["garment_count"] == len(SAMPLE_GARMENTS)
    assert meta["palette_count"] == len(SAMPLE_PALETTES)


def test_the_cutoff_query_parameter_reaches_meta(client, seeded):
    meta = client.get("/color-matches", params={"cutoff": 3.5}).json()["meta"]
    assert meta["cutoff"] == 3.5


def test_the_cutoff_actually_filters(client, seeded):
    loose = client.get("/color-matches", params={"cutoff": 15}).json()
    tight = client.get("/color-matches", params={"cutoff": 1}).json()

    def hits(body):
        return len(body["palettes"]["sage_palette.jpeg"]["matches"][SAGE])

    assert hits(loose) > hits(tight)


def test_a_non_numeric_cutoff_is_a_422(client, seeded):
    response = client.get("/color-matches", params={"cutoff": "close-ish"})
    assert response.status_code == 422


def test_a_negative_cutoff_is_a_422(client, seeded):
    # ΔE is a distance, so below zero can never match anything
    response = client.get("/color-matches", params={"cutoff": -1})
    assert response.status_code == 422


def test_a_cutoff_past_the_ceiling_is_a_422(client, seeded):
    response = client.get("/color-matches", params={"cutoff": 1000})
    assert response.status_code == 422


def test_the_ceiling_itself_is_allowed(client, seeded):
    # the bound is inclusive: ~100 is the largest distance two sRGB colours can
    # be apart, so asking for it is "match everything", not a typo
    assert client.get("/color-matches", params={"cutoff": max_cutoff}).status_code == 200


def test_matches_is_404_when_nothing_is_extracted(client):
    response = client.get("/color-matches")

    assert response.status_code == 404
    assert "no color palettes saved yet" in response.json()["detail"]


def test_matches_is_404_when_only_palettes_exist(client, fake_db):
    fake_db.seed(db.palettes, TEST_USER, SAMPLE_PALETTES)
    response = client.get("/color-matches")

    assert response.status_code == 404
    assert "no clothes saved yet" in response.json()["detail"]


def test_every_garment_entry_carries_colors_and_a_src(client, seeded, fake_storage):
    # "src" is a signed bucket link, minted per request — the UI never builds a
    # photo URL itself, it renders whatever this hands it.
    for entry in client.get("/color-matches").json()["garments"].values():
        assert set(entry) == {"colors", "src"}
        assert entry["src"] is None or entry["src"].startswith("https://")


def test_every_palette_entry_carries_colors_a_src_and_matches(client, seeded, fake_storage):
    for entry in client.get("/color-matches").json()["palettes"].values():
        assert set(entry) == {"colors", "src", "matches"}
        assert entry["src"] is None or entry["src"].startswith("https://")


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


# ----------------------------------------------------- corrupt data storage
#
# /stats is the last route reading the two JSON files; /garments,
# /color-palettes and /color-matches all serve rows. So /stats is the only
# place the JSONDecodeError handler can still fire, and these tests point at
# it rather than at the routes they used to cover. The other half of the
# contract — that a bad file on disk no longer reaches the row-backed routes
# at all — is the last two tests here.

TRUNCATED = '{"sage_shirt.jpeg": ["#B5C29A"'
CORRUPT_DETAIL = "data storage is corrupt; re-run extraction"


def write_corrupt(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TRUNCATED)


def test_a_truncated_garment_store_is_a_500_not_a_traceback(client, data_paths):
    # load_data raises JSONDecodeError rather than reading as {}; the handler
    # turns that into an envelope the UI can render
    write_corrupt(data_paths.garments)
    response = client.get("/stats")

    assert response.status_code == 500
    assert response.json() == {"detail": CORRUPT_DETAIL}


def test_a_truncated_palette_store_is_a_500(client, data_paths):
    write_corrupt(data_paths.palettes)
    response = client.get("/stats")

    assert response.status_code == 500
    assert response.json() == {"detail": CORRUPT_DETAIL}


def test_corruption_is_500_not_the_empty_store_answer(client, data_paths):
    # "re-run extraction" and "you haven't extracted yet" are different fixes,
    # and /stats answers the second one with a 200 and zeroes
    write_corrupt(data_paths.garments)
    assert client.get("/stats").status_code != 200


def test_health_survives_a_corrupt_store(client, data_paths):
    # liveness must not go red just because the JSON on disk is bad
    write_corrupt(data_paths.garments)
    assert client.get("/health").status_code == 200


def test_the_corrupt_response_is_json(client, data_paths):
    write_corrupt(data_paths.garments)
    response = client.get("/stats")
    assert response.headers["content-type"].startswith("application/json")


def test_the_corrupt_response_does_not_leak_the_path(client, data_paths):
    # the detail is user-facing; the filesystem layout stays in the log
    write_corrupt(data_paths.garments)
    assert str(data_paths.garments) not in client.get("/stats").text


def test_corruption_is_logged_with_the_request_path(client, data_paths, caplog):
    write_corrupt(data_paths.garments)
    with caplog.at_level("ERROR", logger="closetllm"):
        client.get("/stats")

    assert any("/stats" in r.getMessage() for r in caplog.records)


def test_a_corrupt_file_no_longer_reaches_the_row_backed_routes(client, seeded):
    # the JSON store is not in the read path any more, so a file nobody can
    # parse is no longer able to take the closet down
    for path in (seeded.garments, seeded.palettes):
        write_corrupt(path)

    assert client.get("/garments").status_code == 200
    assert client.get("/color-palettes").status_code == 200
    assert client.get("/color-matches").status_code == 200


def test_one_corrupt_store_does_not_take_down_the_other(client, seeded):
    write_corrupt(seeded.garments)

    # /stats reads both files, so it goes down with either of them...
    assert client.get("/stats").status_code == 500
    # ...but the routes the UI actually renders are served from rows
    assert client.get("/garments").status_code == 200


# ------------------------------------------------------------ route surface

@pytest.mark.parametrize("path", ["/health", "/stats", "/garments", "/color-palettes", "/color-matches"])
def test_the_documented_routes_exist(client, path):
    assert path in client.app.openapi()["paths"]


@pytest.mark.parametrize("path", ["/health", "/stats", "/garments", "/color-palettes", "/color-matches"])
def test_the_routes_are_get_only(client, path, seeded):
    assert client.post(path).status_code == 405


def test_an_unknown_route_is_404(client):
    assert client.get("/shoes").status_code == 404
