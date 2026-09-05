"""Values pinned against the current implementation.

Nothing here derives a number — each one is the output the code produces today,
either checked against an outside reference (the sRGB/Lab literature, the
Sharma CIEDE2000 test set) or simply frozen. A refactor of the conversion chain
that changes any of them changes which garments match, so the change should be
deliberate.
"""

import pytest

from closetllm import color
from closetllm.color import (
    default_cutoff,
    distance,
    hex_to_lab,
    is_neutral,
    lab_to_lch,
    neutral_chroma,
)


# ------------------------------------------------------- published Lab values

@pytest.mark.parametrize(
    "hex_value, lab",
    [
        # sRGB primaries under D65 — these are textbook values, not ours
        ("#FF0000", (53.2408, 80.0925, 67.2032)),
        ("#00FF00", (87.7347, -86.1827, 83.1793)),
        ("#0000FF", (32.2970, 79.1875, -107.8602)),
        ("#FFFFFF", (100.0, 0.0, 0.0)),
        ("#000000", (0.0, 0.0, 0.0)),
        ("#808080", (53.5850, 0.0, 0.0)),
    ],
)
def test_hex_to_lab_matches_the_published_values(hex_value, lab):
    assert hex_to_lab(hex_value) == pytest.approx(lab, abs=1e-4)


# -------------------------------------------------------------- frozen scores

@pytest.mark.parametrize(
    "hex1, hex2, expected",
    [
        # a garment against its own extracted colour, from the eval set
        ("#96446A", "#C173AB", 18.8021),
        # two near-blacks: small in ΔE2000, much larger in plain Lab distance
        ("#1E1E20", "#2B2B2B", 4.3249),
        # the dark saturated reds the eval calls out as the model's worst case
        ("#9E3134", "#D2305B", 13.0432),
        # two sages, comfortably inside the cutoff
        ("#B5C29A", "#A9B98C", 3.0917),
        ("#7D9681", "#91A193", 5.9694),
    ],
)
def test_frozen_distances(hex1, hex2, expected):
    assert distance(hex1, hex2) == pytest.approx(expected, abs=1e-4)


# ----------------------------------------------------------- tuned constants

def test_the_default_cutoff_is_still_fifteen():
    # tuned on the green garments; it is what decides how generous the UI looks
    assert default_cutoff == 15.0


def test_the_neutral_chroma_threshold_is_still_twelve():
    assert neutral_chroma == 12.0


@pytest.mark.parametrize(
    "hex_value, neutral",
    [
        ("#000000", True),
        ("#FFFFFF", True),
        ("#808080", True),
        ("#1E1E20", True),    # near-black: would otherwise match every dark garment
        ("#B5B0A8", True),    # muted beige, chroma 4.7
        ("#4A4A4A", True),    # a real palette colour, from color_palette_12
        ("#B5C29A", False),   # sage, chroma 21.9
        ("#96446A", False),
        ("#8B5E3C", False),   # brown — low-ish chroma but still a colour
    ],
)
def test_the_neutral_verdict_for_known_colours(hex_value, neutral):
    assert is_neutral(hex_value) is neutral


def test_the_beige_that_sits_closest_to_the_boundary():
    # documents how much headroom the threshold has: raising it past ~4.8 would
    # not change this verdict, lowering it past 4.7 would
    assert lab_to_lch(hex_to_lab("#B5B0A8"))[1] == pytest.approx(4.7340, abs=1e-3)


# ----------------------------------------------------- once-broken edge cases

def test_a_grey_pair_does_not_divide_by_zero():
    # c_bar is 0 for two neutrals; the `if c_bar else 0.5` guard is what saves it
    assert distance("#808080", "#808080") == pytest.approx(0.0)


def test_pure_black_against_pure_black_is_zero_not_nan():
    result = distance("#000000", "#000000")
    assert result == result


def test_a_hue_pair_straddling_zero_degrees_stays_small():
    # the h' wrap-around branches; getting them wrong inflates this to ~350
    assert distance("#FF0011", "#FF0000") < 5.0


def test_the_regex_still_rejects_four_digit_hex():
    # #RGBA is valid CSS and invalid here; silently accepting it would shift
    # every downstream colour
    with pytest.raises(ValueError):
        color.validate_hex_value("#1234")
