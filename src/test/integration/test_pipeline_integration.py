"""Photos in, matched closet out — the whole chain, with the model faked.

The unit tests each hold one piece still. These let the pieces hand data to
each other, and there are two chains to do that along now:

  the CLI    a folder of photos -> the JSON store -> run_matches -> matches.json
  the API    an upload -> a row and an object -> /garments, /color-matches

They share the colour maths in match.py and nothing else: the CLI's closet is
whatever is in data/, the API's is whoever is signed in. A test that mixes
them is testing a path the code no longer has.
"""

import json

import pytest

from closetllm import cli, extract
from closetllm.color import default_cutoff, distance
from closetllm.extract import load_data
from closetllm.match import build_matches, compute_matches

from conftest import NEAR_BLACK, NEAR_SAGE, OLIVE, PINK, NEAR_PINK, SAGE
from helpers import jpeg_bytes


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


def extracted(store) -> dict:
    """compute_matches over whatever the CLI left in the two JSON files."""
    return compute_matches(
        load_data(store.garments), load_data(store.palettes), default_cutoff
    )


# ------------------------------------------------------------ the CLI chain

def test_extract_then_match(closet, jobs_in_tmp, fake_model, capsys):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)

    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    # the stores on disk are what everything downstream reads
    assert json.loads(jobs_in_tmp.garments.read_text())["sage_shirt.jpeg"] == [NEAR_SAGE]
    assert json.loads(jobs_in_tmp.palettes.read_text())["sage_palette.jpeg"] == [SAGE, NEAR_BLACK]

    results = extracted(jobs_in_tmp)

    assert [name for name, _ in results["sage_palette.jpeg"][SAGE]] == [
        "sage_shirt.jpeg",
        "olive_pants.jpeg",
    ]
    assert results["sage_palette.jpeg"][NEAR_BLACK] == []


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

    before = extracted(jobs_in_tmp)["sage_palette.jpeg"][SAGE]

    photo_folder.add("another_sage_top.jpeg")
    fake_model({"item": "top", "color": SAGE})
    extract.run_closet_colors(closet.garments)

    after = extracted(jobs_in_tmp)["sage_palette.jpeg"][SAGE]

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
    # what `match` printed and what it wrote are the same scores
    assert written == json.loads(
        json.dumps(
            build_matches(load_data(jobs_in_tmp.garments), extracted(jobs_in_tmp), default_cutoff)
        )
    )


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


def test_the_written_file_and_the_computed_scores_agree(closet, jobs_in_tmp, fake_model, capsys):
    fake_model(*GARMENT_REPLIES, *PALETTE_REPLIES)
    extract.run_closet_colors(closet.garments)
    extract.run_color_palettes(closet.palettes)

    garments = load_data(jobs_in_tmp.garments)
    results = extracted(jobs_in_tmp)
    doc = build_matches(garments, results, default_cutoff)

    for palette, by_color in results.items():
        for color, hits in by_color.items():
            written = doc["palettes"][palette]["matches"][color]
            assert [h["garment"] for h in written] == [name for name, _ in hits]
            assert [h["score"] for h in written] == [round(s, 2) for _, s in hits]


# ------------------------------------------------------------ the API chain

def upload(client, route, name, content=None):
    return client.post(
        route, files={"file": (name, content or jpeg_bytes(), "image/jpeg")}
    )


def fill_the_closet(client, fake_model):
    """Four garments and two palettes, uploaded the way the UI does it."""
    fake_model(
        {"item": "coat", "color": NEAR_BLACK},
        {"item": "pants", "color": OLIVE},
        {"item": "dress", "color": NEAR_PINK},
        {"item": "shirt", "color": NEAR_SAGE},
        {"colors": [SAGE, NEAR_BLACK]},
        {"colors": [PINK]},
    )
    for name in ("black_coat.jpeg", "olive_pants.jpeg", "pink dress.jpeg", "sage_shirt.jpeg"):
        assert upload(client, "/upload-garments", name).status_code == 201
    for name in ("sage_palette.jpeg", "pink_palette.jpeg"):
        assert upload(client, "/upload-palettes", name).status_code == 201


def test_upload_then_serve(client, upload_paths, fake_model):
    fill_the_closet(client, fake_model)

    body = client.get("/color-matches").json()

    hits = body["palettes"]["sage_palette.jpeg"]["matches"][SAGE]
    assert [h["garment"] for h in hits] == ["sage_shirt.jpeg", "olive_pants.jpeg"]
    assert body["palettes"]["sage_palette.jpeg"]["matches"][NEAR_BLACK] == []


def test_every_uploaded_photo_comes_back_with_a_link(client, upload_paths, fake_model):
    # the row carries the key, the bucket carries the bytes, and the response
    # carries a signed link joining them — a break anywhere is a null here
    fill_the_closet(client, fake_model)

    body = client.get("/color-matches").json()

    for section in ("garments", "palettes"):
        for name, entry in body[section].items():
            assert entry["src"] is not None, name
            assert entry["src"].startswith("https://")


def test_the_api_picks_up_photos_uploaded_after_it_started(client, upload_paths, fake_model):
    # nothing is cached in module state, so a fresh upload is visible to the
    # next request without a restart
    assert client.get("/garments").status_code == 404

    fake_model({"item": "shirt", "color": NEAR_SAGE})
    upload(client, "/upload-garments", "sage_shirt.jpeg")

    assert client.get("/garments").json() == {
        "count": 1,
        "garments": {"sage_shirt.jpeg": [NEAR_SAGE]},
    }


def test_one_users_upload_is_invisible_to_another(client, upload_paths, fake_model):
    # the whole reason the rows are owned; the closet is not a shared folder
    from closetllm import db
    from helpers import TEST_USER

    fake_model({"item": "shirt", "color": NEAR_SAGE})
    upload(client, "/upload-garments", "sage_shirt.jpeg")

    assert upload_paths.db.load_user_colors(db.garments, TEST_USER) == {
        "sage_shirt.jpeg": [NEAR_SAGE]
    }
    assert upload_paths.db.load_user_colors(db.garments, "someone-else") == {}


def test_the_cutoff_travels_from_the_query_string_to_the_scores(client, upload_paths, fake_model):
    fill_the_closet(client, fake_model)

    olive_score = distance(SAGE, OLIVE)

    just_under = client.get("/color-matches", params={"cutoff": olive_score - 0.01}).json()
    just_over = client.get("/color-matches", params={"cutoff": olive_score + 0.01}).json()

    def names(body):
        return [h["garment"] for h in body["palettes"]["sage_palette.jpeg"]["matches"][SAGE]]

    assert "olive_pants.jpeg" not in names(just_under)
    assert "olive_pants.jpeg" in names(just_over)


def test_a_failed_upload_leaves_the_closet_exactly_as_it_was(client, upload_paths, fake_model):
    fake_model({"item": "shirt", "color": NEAR_SAGE}, {"colors": []})
    upload(client, "/upload-garments", "sage_shirt.jpeg")
    before = client.get("/garments").json()

    assert upload(client, "/upload-palettes", "inspo.jpeg").status_code == 502

    assert client.get("/garments").json() == before
    assert client.get("/color-palettes").status_code == 404
    assert len(upload_paths.storage.files) == 1
