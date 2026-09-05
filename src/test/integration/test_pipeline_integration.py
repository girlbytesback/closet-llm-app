"""Photos in, matched closet out — the whole chain, with the model faked.

The unit tests each hold one piece still. These let the pieces hand data to
each other: the JSON one stage writes is the JSON the next stage reads, and the
API serves what the CLI produced.
"""

import json

import pytest
from fastapi.testclient import TestClient

from closetllm import api, cli, extract
from closetllm.color import default_cutoff, distance
from closetllm.match import build_matches, compute_matches

from conftest import NEAR_BLACK, NEAR_SAGE, OLIVE, PINK, NEAR_PINK, SAGE


@pytest.fixture
def closet(photo_folder, tmp_path):
    """Two folders of real photos: a closet and a wall of Pinterest palettes."""
    from PIL import Image

    palettes = tmp_path / "palettes"
    palettes.mkdir()
    for name in ("sage_palette.jpeg", "pink_palette.jpeg"):
        Image.new("RGB", (40, 40), (180, 194, 154)).save(palettes / name)

    for name in ("black_coat.jpeg", "olive_pants.jpeg", "pink dress.jpeg", "sage_shirt.jpeg"):
        photo_folder.add(name)

    return type("Folders", (), {"garments": photo_folder.path, "palettes": palettes})


# extraction order follows sorted(folder.iterdir())
GARMENT_REPLIES = [
    {"item": "coat", "color": NEAR_BLACK},
    {"item": "pants", "color": OLIVE},
    {"item": "dress", "color": NEAR_PINK},
    {"item": "shirt", "color": NEAR_SAGE},
]
PALETTE_REPLIES = [
    {"colors": [PINK]},                 # pink_palette.jpeg sorts first
    {"colors": [SAGE, NEAR_BLACK]},
]


def test_extract_then_match_then_serve(closet, jobs_in_tmp, fake_model, capsys):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)

    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    # the stores on disk are what everything downstream reads
    assert json.loads(jobs_in_tmp.garments.read_text())["sage_shirt.jpeg"] == [NEAR_SAGE]
    assert json.loads(jobs_in_tmp.palettes.read_text())["sage_palette.jpeg"] == [SAGE, NEAR_BLACK]

    body = TestClient(api.app).get("/color-matches").json()

    hits = body["palettes"]["sage_palette.jpeg"]["matches"][SAGE]
    assert [h["garment"] for h in hits] == ["sage_shirt.jpeg", "olive_pants.jpeg"]
    assert body["palettes"]["sage_palette.jpeg"]["matches"][NEAR_BLACK] == []
    assert body["garments"]["pink dress.jpeg"]["src"] == "/clothes/pink%20dress.jpeg"


def test_the_second_extraction_run_costs_nothing(closet, jobs_in_tmp, fake_model, capsys):
    # the cache is the whole reason the JSON is committed: one model call per
    # photo, ever
    messages = fake_model(*GARMENT_REPLIES)
    extract.run_closet_colors(closet.garments)
    assert len(messages.calls) == 4

    messages = fake_model()  # any call now fails the test
    second = extract.run_closet_colors(closet.garments)

    assert messages.calls == []
    assert second == json.loads(jobs_in_tmp.garments.read_text())


def test_a_new_photo_only_costs_one_call(closet, jobs_in_tmp, fake_model, photo_folder, capsys):
    fake_model(*GARMENT_REPLIES)
    extract.run_closet_colors(closet.garments)

    photo_folder.add("zebra_scarf.jpeg")
    messages = fake_model({"item": "scarf", "color": "#B7C39B"})
    result = extract.run_closet_colors(closet.garments)

    assert len(messages.calls) == 1
    assert result["zebra_scarf.jpeg"] == ["#B7C39B"]


def test_a_new_garment_shows_up_in_the_matches(closet, jobs_in_tmp, fake_model, photo_folder, capsys):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)
    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    before = compute_matches()["sage_palette.jpeg"][SAGE]

    photo_folder.add("another_sage_top.jpeg")
    fake_model({"item": "top", "color": SAGE})
    extract.run_closet_colors(closet.garments)

    after = compute_matches()["sage_palette.jpeg"][SAGE]

    assert len(after) == len(before) + 1
    assert after[0][0] == "another_sage_top.jpeg"   # an exact match sorts first


def test_an_interrupted_extraction_resumes_where_it_stopped(
    closet, jobs_in_tmp, fake_model, capsys
):
    # photo three comes back unparseable; the first two calls must survive
    fake_model(GARMENT_REPLIES[0], GARMENT_REPLIES[1], {"item": "dress", "color": "pink-ish"})

    with pytest.raises(ValueError):
        extract.run_closet_colors(closet.garments)

    assert set(json.loads(jobs_in_tmp.garments.read_text())) == {
        "black_coat.jpeg",
        "olive_pants.jpeg",
    }

    # rerun with a good reply: only the two unfinished photos are paid for
    messages = fake_model(GARMENT_REPLIES[2], GARMENT_REPLIES[3])
    extract.run_closet_colors(closet.garments)

    assert len(messages.calls) == 2


def test_the_cli_runs_the_whole_thing_end_to_end(
    closet, jobs_in_tmp, fake_model, monkeypatch, tmp_path, capsys
):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)
    out = tmp_path / "matches.json"

    for argv in (
        ["closetllm", "clothes", str(closet.garments)],
        ["closetllm", "palettes", str(closet.palettes)],
        ["closetllm", "match", "--out", str(out)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        cli.main()

    printed = capsys.readouterr().out
    written = json.loads(out.read_text())

    assert "sage_shirt.jpeg" in printed
    assert written["meta"]["garment_count"] == 4
    assert written["meta"]["palette_count"] == 2
    assert written == TestClient(api.app).get("/color-matches").json()


def test_the_cli_reports_a_missing_folder_without_a_traceback(monkeypatch, jobs_in_tmp, tmp_path):
    monkeypatch.setattr("sys.argv", ["closetllm", "clothes", str(tmp_path / "nope")])

    with pytest.raises(SystemExit) as exit_:
        cli.main()

    assert "no photos folder at" in str(exit_.value)


def test_matching_before_extracting_is_a_clean_error(jobs_in_tmp, monkeypatch):
    monkeypatch.setattr("sys.argv", ["closetllm", "match"])

    with pytest.raises(SystemExit) as exit_:
        cli.main()

    assert "no color palettes saved yet" in str(exit_.value)


def test_the_api_picks_up_data_written_after_it_started(closet, jobs_in_tmp, fake_model, capsys):
    # nothing is cached in module state, so a fresh extraction is visible to
    # the next request without a restart
    http = TestClient(api.app)
    assert http.get("/garments").status_code == 404

    fake_model(*GARMENT_REPLIES)
    extract.run_closet_colors(closet.garments)

    assert http.get("/garments").json()["count"] == 4


def test_the_threshold_travels_from_the_query_string_to_the_scores(
    closet, jobs_in_tmp, fake_model, capsys
):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)
    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    http = TestClient(api.app)
    olive_score = distance(SAGE, OLIVE)

    just_under = http.get("/color-matches", params={"threshold": olive_score - 0.01}).json()
    just_over = http.get("/color-matches", params={"threshold": olive_score + 0.01}).json()

    def names(body):
        return [h["garment"] for h in body["palettes"]["sage_palette.jpeg"]["matches"][SAGE]]

    assert "olive_pants.jpeg" not in names(just_under)
    assert "olive_pants.jpeg" in names(just_over)


def test_the_written_file_and_the_computed_scores_agree(closet, jobs_in_tmp, fake_model, capsys):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)
    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    results = compute_matches()
    doc = build_matches(results, default_cutoff)

    for palette, by_color in results.items():
        for color, hits in by_color.items():
            written = doc["palettes"][palette]["matches"][color]
            assert [h["garment"] for h in written] == [name for name, _ in hits]
            assert [h["score"] for h in written] == [round(s, 2) for _, s in hits]
