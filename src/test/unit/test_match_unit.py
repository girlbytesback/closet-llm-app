"""match.py: compute_matches thinks, the other three consume its output."""

import json

import pytest

from closetllm.color import default_cutoff, distance
from closetllm.match import (
    build_matches,
    compute_matches,
    print_matches,
    run_matches,
    write_matches,
)
from closetllm.extract import save_data

from conftest import NEAR_BLACK, NEAR_SAGE, OLIVE, PINK, SAGE, SAMPLE_GARMENTS


# -------------------------------------------------------------- compute_matches

def test_compute_matches_raises_when_no_palettes_are_saved(data_paths):
    save_data(SAMPLE_GARMENTS, data_paths.garments)

    with pytest.raises(FileNotFoundError, match="no color palettes saved yet"):
        compute_matches()


def test_compute_matches_raises_when_no_garments_are_saved(data_paths):
    save_data({"p.jpeg": [SAGE]}, data_paths.palettes)

    with pytest.raises(FileNotFoundError, match="no clothes saved yet"):
        compute_matches()


def test_compute_matches_keys_by_palette_then_by_palette_colour(seeded):
    results = compute_matches()

    assert set(results) == {"sage_palette.jpeg", "pink_palette.jpeg"}
    assert list(results["sage_palette.jpeg"]) == [SAGE, NEAR_BLACK]


def test_compute_matches_returns_garments_closest_first(seeded):
    hits = compute_matches()["sage_palette.jpeg"][SAGE]

    assert [name for name, _ in hits] == ["sage_shirt.jpeg", "olive_pants.jpeg"]
    assert hits[0][1] < hits[1][1]


def test_compute_matches_scores_against_the_real_distance(seeded):
    hits = dict(compute_matches()["sage_palette.jpeg"][SAGE])
    assert hits["sage_shirt.jpeg"] == pytest.approx(distance(SAGE, NEAR_SAGE))


def test_a_neutral_palette_colour_keeps_its_slot_but_matches_nothing(seeded):
    # a near-black in a palette would otherwise match every dark garment owned
    results = compute_matches()

    assert NEAR_BLACK in results["sage_palette.jpeg"]
    assert results["sage_palette.jpeg"][NEAR_BLACK] == []


def test_a_tighter_threshold_drops_the_looser_match(seeded):
    tight = compute_matches(threshold=1.0)["sage_palette.jpeg"][SAGE]
    assert [name for name, _ in tight] == ["sage_shirt.jpeg"]


def test_a_zero_threshold_matches_nothing(seeded):
    results = compute_matches(threshold=0.0)
    assert all(hits == [] for by_color in results.values() for hits in by_color.values())


def test_the_default_threshold_is_the_shared_cutoff(seeded):
    assert compute_matches() == compute_matches(default_cutoff)


def test_palettes_come_back_in_sorted_order(seeded):
    assert list(compute_matches()) == sorted(compute_matches())


# ---------------------------------------------------------------- build_matches

def test_build_matches_reports_the_cutoff_it_was_given(seeded):
    doc = build_matches(compute_matches(9.0), 9.0)
    assert doc["meta"]["cutoff"] == 9.0


def test_build_matches_counts_garments_and_palettes(seeded):
    doc = build_matches(compute_matches(), default_cutoff)

    assert doc["meta"]["garment_count"] == len(SAMPLE_GARMENTS)
    assert doc["meta"]["palette_count"] == 2


def test_build_matches_lists_every_garment_not_just_the_matching_ones(seeded):
    # the UI renders the whole closet and highlights the hits
    doc = build_matches(compute_matches(), default_cutoff)
    assert set(doc["garments"]) == set(SAMPLE_GARMENTS)


def test_a_garment_carries_its_colours_and_an_image_url(seeded):
    doc = build_matches(compute_matches(), default_cutoff)

    assert doc["garments"]["sage_shirt.jpeg"] == {
        "colors": [NEAR_SAGE],
        "src": "/clothes/sage_shirt.jpeg",
    }


def test_a_space_in_a_filename_is_percent_encoded(seeded):
    # an unquoted space breaks the <img src> in the browser
    doc = build_matches(compute_matches(), default_cutoff)
    assert doc["garments"]["pink dress.jpeg"]["src"] == "/clothes/pink%20dress.jpeg"


def test_a_palette_carries_its_colours_in_order(seeded):
    doc = build_matches(compute_matches(), default_cutoff)
    assert doc["palettes"]["sage_palette.jpeg"]["colors"] == [SAGE, NEAR_BLACK]


def test_scores_are_rounded_to_two_places(seeded):
    # full float precision is noise on a 0-30 range and triples the file size
    doc = build_matches(compute_matches(), default_cutoff)
    hits = doc["palettes"]["sage_palette.jpeg"]["matches"][SAGE]

    for hit in hits:
        assert hit["score"] == round(hit["score"], 2)


def test_a_match_names_the_garment_and_the_score(seeded):
    doc = build_matches(compute_matches(), default_cutoff)
    first = doc["palettes"]["sage_palette.jpeg"]["matches"][SAGE][0]

    assert first == {"garment": "sage_shirt.jpeg", "score": round(distance(SAGE, NEAR_SAGE), 2)}


def test_build_matches_preserves_the_closest_first_ordering(seeded):
    doc = build_matches(compute_matches(), default_cutoff)
    scores = [h["score"] for h in doc["palettes"]["sage_palette.jpeg"]["matches"][SAGE]]

    assert scores == sorted(scores)


def test_build_matches_survives_an_empty_result_set(seeded):
    doc = build_matches({}, default_cutoff)

    assert doc["palettes"] == {}
    assert doc["meta"]["palette_count"] == 0
    # the closet is still there — it is read from disk, not from the results
    assert doc["garments"]


# ---------------------------------------------------------------- write_matches

def test_write_matches_writes_readable_json(seeded, tmp_path):
    out = tmp_path / "ui" / "matches.json"
    write_matches(compute_matches(), out, default_cutoff)

    assert json.loads(out.read_text())["meta"]["cutoff"] == default_cutoff


def test_write_matches_creates_missing_directories(seeded, tmp_path):
    out = tmp_path / "deeply" / "nested" / "matches.json"
    write_matches(compute_matches(), out, default_cutoff)
    assert out.exists()


# ---------------------------------------------------------------- print_matches

def test_print_matches_prints_a_header_per_palette(seeded, capsys):
    print_matches(compute_matches(), default_cutoff)
    out = capsys.readouterr().out

    assert "sage_palette.jpeg" in out
    assert "pink_palette.jpeg" in out


def test_print_matches_lists_each_hit_with_its_score(seeded, capsys):
    print_matches(compute_matches(), default_cutoff)
    out = capsys.readouterr().out

    assert "sage_shirt.jpeg" in out
    assert "olive_pants.jpeg" in out


def test_print_matches_says_so_when_a_palette_has_nothing(seeded, capsys):
    print_matches(compute_matches(0.0), 0.0)
    assert "nothing under 0" in capsys.readouterr().out


def test_print_matches_dashes_a_colour_with_no_hits(seeded, capsys):
    # the neutral colour is skipped, but the palette as a whole has matches,
    # so we get the per-colour dash rather than the whole-palette message
    print_matches(compute_matches(), default_cutoff)
    assert "—" in capsys.readouterr().out


def test_print_matches_limit_caps_the_rows_per_colour(seeded, capsys):
    print_matches(compute_matches(), default_cutoff, limit=1)
    out = capsys.readouterr().out

    assert "sage_shirt.jpeg" in out
    assert "olive_pants.jpeg" not in out


def test_print_matches_does_not_touch_the_results(seeded):
    results = compute_matches()
    before = json.dumps(results, sort_keys=True, default=list)
    print_matches(results, default_cutoff, limit=1)

    assert json.dumps(results, sort_keys=True, default=list) == before


# ------------------------------------------------------------------ run_matches

def test_run_matches_returns_the_scores_and_prints_them(seeded, capsys):
    results = run_matches()

    assert results == compute_matches()
    assert "sage_palette.jpeg" in capsys.readouterr().out


def test_run_matches_writes_nothing_unless_asked(seeded, tmp_path, capsys):
    run_matches()
    assert list(tmp_path.glob("**/matches.json")) == []


def test_run_matches_writes_the_file_and_says_where(seeded, tmp_path, capsys):
    out = tmp_path / "matches.json"
    run_matches(out=out)

    assert out.exists()
    assert f"wrote {out}" in capsys.readouterr().out


def test_run_matches_cuts_the_printout_and_the_file_at_the_same_threshold(
    seeded, tmp_path, capsys
):
    out = tmp_path / "matches.json"
    run_matches(threshold=1.0, out=out)

    printed = capsys.readouterr().out
    written = json.loads(out.read_text())

    assert written["meta"]["cutoff"] == 1.0
    assert "olive_pants.jpeg" not in printed
    assert written["palettes"]["sage_palette.jpeg"]["matches"][SAGE] == [
        {"garment": "sage_shirt.jpeg", "score": round(distance(SAGE, NEAR_SAGE), 2)}
    ]
