"""match.py: compute_matches thinks, the other three consume its output.

compute_matches is handed the two dicts rather than reading them, so these
tests pass the samples in directly — no store of any kind is involved. The one
exception is run_matches, which is the CLI's entry point and does read the JSON
files; `seeded` is what puts them there.
"""

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

from conftest import (
    NEAR_BLACK,
    NEAR_SAGE,
    SAGE,
    SAMPLE_GARMENTS,
    SAMPLE_PALETTES,
)


def matches(cutoff=default_cutoff, garments=None, palettes=None):
    """compute_matches over the samples — the argument every test below shares."""
    return compute_matches(
        SAMPLE_GARMENTS if garments is None else garments,
        SAMPLE_PALETTES if palettes is None else palettes,
        cutoff,
    )


def document(cutoff=default_cutoff):
    return build_matches(SAMPLE_GARMENTS, matches(cutoff), cutoff)


# -------------------------------------------------------------- compute_matches

def test_compute_matches_raises_when_no_palettes_are_saved():
    with pytest.raises(FileNotFoundError, match="no color palettes saved yet"):
        compute_matches(SAMPLE_GARMENTS, {}, default_cutoff)


def test_compute_matches_raises_when_no_garments_are_saved():
    with pytest.raises(FileNotFoundError, match="no clothes saved yet"):
        compute_matches({}, {"p.jpeg": [SAGE]}, default_cutoff)


def test_an_empty_everything_names_the_palettes_first():
    # both are missing, and "go extract some inspiration" is the more useful of
    # the two answers; the API turns whichever comes out into the 404 detail
    with pytest.raises(FileNotFoundError, match="no color palettes saved yet"):
        compute_matches({}, {}, default_cutoff)


def test_compute_matches_keys_by_palette_then_by_palette_colour():
    results = matches()

    assert set(results) == {"sage_palette.jpeg", "pink_palette.jpeg"}
    assert list(results["sage_palette.jpeg"]) == [SAGE, NEAR_BLACK]


def test_compute_matches_returns_garments_closest_first():
    hits = matches()["sage_palette.jpeg"][SAGE]

    assert [name for name, _ in hits] == ["sage_shirt.jpeg", "olive_pants.jpeg"]
    assert hits[0][1] < hits[1][1]


def test_compute_matches_scores_against_the_real_distance():
    hits = dict(matches()["sage_palette.jpeg"][SAGE])
    assert hits["sage_shirt.jpeg"] == pytest.approx(distance(SAGE, NEAR_SAGE))


def test_compute_matches_reads_nothing_off_disk(data_paths):
    # it used to load the JSON stores and ignore its arguments, which made the
    # API serve one user's rows scored against another closet entirely
    other = {"only_garment.jpeg": [NEAR_SAGE]}

    results = compute_matches(other, {"p.jpeg": [SAGE]}, default_cutoff)

    assert [name for name, _ in results["p.jpeg"][SAGE]] == ["only_garment.jpeg"]


def test_a_neutral_palette_colour_keeps_its_slot_but_matches_nothing():
    # a near-black in a palette would otherwise match every dark garment owned
    results = matches()

    assert NEAR_BLACK in results["sage_palette.jpeg"]
    assert results["sage_palette.jpeg"][NEAR_BLACK] == []


def test_a_tighter_cutoff_drops_the_looser_match():
    tight = matches(cutoff=1.0)["sage_palette.jpeg"][SAGE]
    assert [name for name, _ in tight] == ["sage_shirt.jpeg"]


def test_a_zero_cutoff_matches_nothing():
    results = matches(cutoff=0.0)
    assert all(hits == [] for by_color in results.values() for hits in by_color.values())


def test_the_default_cutoff_is_the_shared_cutoff():
    assert compute_matches(SAMPLE_GARMENTS, SAMPLE_PALETTES) == matches(default_cutoff)


def test_palettes_come_back_in_sorted_order():
    assert list(matches()) == sorted(matches())


# ---------------------------------------------------------------- build_matches

def test_build_matches_reports_the_cutoff_it_was_given():
    assert document(9.0)["meta"]["cutoff"] == 9.0


def test_build_matches_counts_garments_and_palettes():
    doc = document()

    assert doc["meta"]["garment_count"] == len(SAMPLE_GARMENTS)
    assert doc["meta"]["palette_count"] == 2


def test_build_matches_lists_every_garment_not_just_the_matching_ones():
    # the UI renders the whole closet and highlights the hits
    assert set(document()["garments"]) == set(SAMPLE_GARMENTS)


def test_a_garment_carries_only_its_colours():
    # no "src": build_matches is the colour maths and does not know where a
    # photo lives. api.py adds the key from the signed bucket links.
    assert document()["garments"]["sage_shirt.jpeg"] == {"colors": [NEAR_SAGE]}


def test_a_palette_carries_its_colours_in_order():
    assert document()["palettes"]["sage_palette.jpeg"]["colors"] == [SAGE, NEAR_BLACK]


def test_scores_are_rounded_to_two_places():
    # full float precision is noise on a 0-30 range and triples the file size
    for hit in document()["palettes"]["sage_palette.jpeg"]["matches"][SAGE]:
        assert hit["score"] == round(hit["score"], 2)


def test_a_match_names_the_garment_and_the_score():
    first = document()["palettes"]["sage_palette.jpeg"]["matches"][SAGE][0]

    assert first == {"garment": "sage_shirt.jpeg", "score": round(distance(SAGE, NEAR_SAGE), 2)}


def test_build_matches_preserves_the_closest_first_ordering():
    scores = [h["score"] for h in document()["palettes"]["sage_palette.jpeg"]["matches"][SAGE]]

    assert scores == sorted(scores)


def test_build_matches_survives_an_empty_result_set():
    doc = build_matches(SAMPLE_GARMENTS, {}, default_cutoff)

    assert doc["palettes"] == {}
    assert doc["meta"]["palette_count"] == 0
    # the closet is still there — it comes in as its own argument, not out of
    # the results
    assert doc["garments"]


def test_build_matches_counts_the_closet_it_was_handed():
    # the count used to come from the JSON store regardless of who asked, so
    # every user saw the same garment_count
    doc = build_matches({"one.jpeg": [SAGE]}, matches(), default_cutoff)

    assert doc["meta"]["garment_count"] == 1
    assert set(doc["garments"]) == {"one.jpeg"}


# ---------------------------------------------------------------- write_matches

def test_write_matches_writes_readable_json(tmp_path):
    out = tmp_path / "ui" / "matches.json"
    write_matches(SAMPLE_GARMENTS, matches(), out, default_cutoff)

    assert json.loads(out.read_text())["meta"]["cutoff"] == default_cutoff


def test_write_matches_creates_missing_directories(tmp_path):
    out = tmp_path / "deeply" / "nested" / "matches.json"
    write_matches(SAMPLE_GARMENTS, matches(), out, default_cutoff)
    assert out.exists()


# ---------------------------------------------------------------- print_matches

def test_print_matches_prints_a_header_per_palette(capsys):
    print_matches(matches(), default_cutoff)
    out = capsys.readouterr().out

    assert "sage_palette.jpeg" in out
    assert "pink_palette.jpeg" in out


def test_print_matches_lists_each_hit_with_its_score(capsys):
    print_matches(matches(), default_cutoff)
    out = capsys.readouterr().out

    assert "sage_shirt.jpeg" in out
    assert "olive_pants.jpeg" in out


def test_print_matches_says_so_when_a_palette_has_nothing(capsys):
    print_matches(matches(0.0), 0.0)
    assert "nothing under 0" in capsys.readouterr().out


def test_print_matches_dashes_a_colour_with_no_hits(capsys):
    # the neutral colour is skipped, but the palette as a whole has matches,
    # so we get the per-colour dash rather than the whole-palette message
    print_matches(matches(), default_cutoff)
    assert "—" in capsys.readouterr().out


def test_print_matches_limit_caps_the_rows_per_colour(capsys):
    print_matches(matches(), default_cutoff, limit=1)
    out = capsys.readouterr().out

    assert "sage_shirt.jpeg" in out
    assert "olive_pants.jpeg" not in out


def test_print_matches_does_not_touch_the_results():
    results = matches()
    before = json.dumps(results, sort_keys=True, default=list)
    print_matches(results, default_cutoff, limit=1)

    assert json.dumps(results, sort_keys=True, default=list) == before


# ------------------------------------------------------------------ run_matches
#
# The CLI's entry point, and the one function here that reads a store: it loads
# the two JSON files `closetllm clothes` and `closetllm palettes` wrote. The
# API never calls it — it passes rows to compute_matches directly.

def test_run_matches_scores_what_the_cli_extracted(seeded, capsys):
    results = run_matches()

    assert results == matches()
    assert "sage_palette.jpeg" in capsys.readouterr().out


def test_run_matches_raises_before_anything_is_extracted(data_paths):
    with pytest.raises(FileNotFoundError, match="no color palettes saved yet"):
        run_matches()


def test_run_matches_writes_nothing_unless_asked(seeded, tmp_path, capsys):
    run_matches()
    assert list(tmp_path.glob("**/matches.json")) == []


def test_run_matches_writes_the_file_and_says_where(seeded, tmp_path, capsys):
    out = tmp_path / "matches.json"
    run_matches(out=out)

    assert out.exists()
    assert f"wrote {out}" in capsys.readouterr().out


def test_run_matches_cuts_the_printout_and_the_file_at_the_same_cutoff(
    seeded, tmp_path, capsys
):
    out = tmp_path / "matches.json"
    run_matches(cutoff=1.0, out=out)

    printed = capsys.readouterr().out
    written = json.loads(out.read_text())

    assert written["meta"]["cutoff"] == 1.0
    assert "olive_pants.jpeg" not in printed
    assert written["palettes"]["sage_palette.jpeg"]["matches"][SAGE] == [
        {"garment": "sage_shirt.jpeg", "score": round(distance(SAGE, NEAR_SAGE), 2)}
    ]
