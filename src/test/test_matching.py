import pytest

from closetllm.color import (
    hue_gap,
    is_neutral,
    matches_for_color,
    matches_for_color_palette,
    neutral_chroma,
    score_garment,
)

RED = "#FF0000"
NEAR_RED = "#FE0000"      # visually identical to RED
MID_RED = "#DD2222"       # clearly related, still close
GREEN = "#00FF00"         # far from RED
GRAY = "#808080"          # neutral: zero chroma

def test_similar_matches_order():
    garments = {"far": [GREEN], "near": [NEAR_RED], "mid": [MID_RED]}
    names = [name for name, _ in matches_for_color(RED, garments)]
    assert names == ["near", "mid"]

def test_threshold_cutoff():
    garments = {"near": [NEAR_RED], "mid": [MID_RED]}
    generous = matches_for_color(RED, garments, cutoff=50.0)
    strict   = matches_for_color(RED, garments, cutoff=1.0)
    assert len(generous) == 2
    assert [name for name, _ in strict] == ["near"]

def test_is_neutral():
    garments = {"near": [NEAR_RED], "dark": ["#1E1E20"]}
    results = matches_for_color_palette([GRAY], garments)
    assert results[GRAY] == []

@pytest.mark.parametrize("gray", ["#000000", "#808080", "#FFFFFF"])
def test_grays_are_neutral(gray):
    assert is_neutral(gray) is True


@pytest.mark.parametrize("colored", ["#FF0000", "#C275AC", "#1B3671"])
def test_saturated_colors_are_not_neutral(colored):
    assert is_neutral(colored) is False


def test_muted_beige_reads_as_neutral():
    # low-chroma but not literally grey — the case the docstring calls out
    assert is_neutral("#B5B0A8") is True


def test_neutral_cutoff_is_the_boundary_that_decides():
    # documents the dependency: is_neutral is a threshold call on chroma, so a
    # change to neutral_chroma is a behavior change, not a tuning detail
    from closetllm.color import hex_to_lab, lab_to_lch

    assert lab_to_lch(hex_to_lab("#B5B0A8"))[1] < neutral_chroma
    assert lab_to_lch(hex_to_lab("#C275AC"))[1] > neutral_chroma

def test_matches_are_sorted_closest_first():
    garments = {"far": [GREEN], "near": [NEAR_RED], "mid": [MID_RED]}
    names = [name for name, _ in matches_for_color(RED, garments)]
    assert names == ["near", "mid"]

def test_cutoff_excludes_anything_above_the_threshold():
    garments = {"near": [NEAR_RED], "mid": [MID_RED]}

    generous = matches_for_color(RED, garments, cutoff=50.0)
    strict = matches_for_color(RED, garments, cutoff=1.0)

    assert len(generous) == 2
    assert [name for name, _ in strict] == ["near"]


def test_no_matches_returns_empty_list_not_none():
    # downstream code iterates this; None would raise instead of yielding nothing
    assert matches_for_color(RED, {"far": [GREEN]}, cutoff=1.0) == []
