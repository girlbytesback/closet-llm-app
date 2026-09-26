"""/color-matches when one side of the closet (or both) is empty.

The UI has one data source, /color-matches, and it used to 404 until both
tables had rows. Uploading clothes first therefore rendered "your closet is
empty" — the rows were there, the document just refused to include them.
These pin the new contract: always 200, carrying whatever exists.

Drop into src/test/contract/. Replaces these two in test_api_contract.py,
which assert the old 404 and must be deleted:
    test_matches_is_404_when_nothing_is_extracted
    test_matches_is_404_when_only_palettes_exist
"""

from closetllm import db
from closetllm.color import default_cutoff

from conftest import SAMPLE_GARMENTS, SAMPLE_PALETTES
from helpers import TEST_USER


def test_nothing_uploaded_is_200_and_empty(client):
    response = client.get("/color-matches")

    assert response.status_code == 200
    assert response.json() == {
        "meta": {"cutoff": default_cutoff, "garment_count": 0, "palette_count": 0},
        "garments": {},
        "palettes": {},
    }


def test_only_garments_lists_the_closet_with_no_palettes(client, fake_db):
    # what the "my clothing" window draws before any inspo exists
    fake_db.seed(db.garments, TEST_USER, SAMPLE_GARMENTS)

    body = client.get("/color-matches").json()

    assert set(body["garments"]) == set(SAMPLE_GARMENTS)
    assert body["palettes"] == {}
    assert body["meta"]["garment_count"] == len(SAMPLE_GARMENTS)
    assert body["meta"]["palette_count"] == 0


def test_only_palettes_lists_them_with_empty_match_lists(client, fake_db):
    # the palette strip renders and every swatch says NO MATCH
    fake_db.seed(db.palettes, TEST_USER, SAMPLE_PALETTES)

    body = client.get("/color-matches").json()

    assert body["garments"] == {}
    assert set(body["palettes"]) == set(SAMPLE_PALETTES)
    for name, palette in body["palettes"].items():
        assert palette["colors"] == SAMPLE_PALETTES[name]
        assert all(hits == [] for hits in palette["matches"].values())
