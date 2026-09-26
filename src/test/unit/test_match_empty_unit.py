"""compute_matches on an empty side, and where the "nothing saved yet" errors went.

compute_matches used to raise FileNotFoundError when either dict was empty,
which made /color-matches a 404 until BOTH tables had rows — a closet with
clothes but no inspo (or the other way round) rendered as "empty" even though
the rows were there. The maths never needed the guard: no palettes gives {},
no garments gives every swatch an empty hit list. The guard now lives in
run_matches, the CLI path, which is the one caller that wants a sentence
instead of an empty document.

Drop into src/test/unit/. Replaces these three in test_match_unit.py, which
assert the old behaviour and must be deleted:
    test_compute_matches_raises_when_no_palettes_are_saved
    test_compute_matches_raises_when_no_garments_are_saved
    test_an_empty_everything_names_the_palettes_first
(test_run_matches_raises_before_anything_is_extracted stays: it covers the
no-palettes message on the CLI path, which is unchanged.)
"""

import pytest

from closetllm.color import default_cutoff
from closetllm.extract import save_data
from closetllm.match import compute_matches, run_matches

from conftest import NEAR_BLACK, SAGE, SAMPLE_GARMENTS, SAMPLE_PALETTES


# -------------------------------------------------------------- compute_matches

def test_no_palettes_is_an_empty_document_not_an_error():
    assert compute_matches(SAMPLE_GARMENTS, {}, default_cutoff) == {}


def test_no_garments_keeps_every_swatch_with_no_hits():
    # the UI draws one row per palette colour, so every key has to be there —
    # a missing swatch would read as "this colour was never extracted"
    results = compute_matches({}, SAMPLE_PALETTES, default_cutoff)

    assert set(results) == set(SAMPLE_PALETTES)
    assert results["sage_palette.jpeg"] == {SAGE: [], NEAR_BLACK: []}


def test_nothing_at_all_is_an_empty_document():
    assert compute_matches({}, {}, default_cutoff) == {}


# ------------------------------------------------------------------ run_matches

def test_run_matches_still_refuses_with_no_garments(data_paths):
    # the CLI keeps its sentence; only the API stopped treating this as an error
    save_data(SAMPLE_PALETTES, data_paths.palettes)

    with pytest.raises(FileNotFoundError, match="no clothes saved yet"):
        run_matches()
