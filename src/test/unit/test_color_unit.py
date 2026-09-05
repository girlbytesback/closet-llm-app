"""The colour conversion chain, one link at a time.

test_color_calculations.py already checks CIEDE2000 against the Sharma
reference set and the hex validator's happy path. This file covers the links
in between, and the properties the matching code leans on.
"""

import pytest

from closetllm.color import (
    color_distance,
    distance,
    hex_to_lab,
    hex_to_rgb,
    hue_gap,
    lab_to_lch,
    raw_distance,
    rgb_to_xyz,
    score_garment,
    validate_hex_value,
    xyz_to_lab,
)


# ---------------------------------------------------------- validate_hex_value

@pytest.mark.parametrize(
    "value, expected",
    [
        ("#B5C29A", "#B5C29A"),
        ("b5c29a", "#B5C29A"),      # the model sometimes drops the hash
        ("#b5c29a", "#B5C29A"),     # and sometimes lowercases
        ("  #B5C29A  ", "#B5C29A"),
        ("#FFF", "#FFFFFF"),
        ("fff", "#FFFFFF"),
        ("#012", "#001122"),
    ],
)
def test_accepted_forms_normalize_to_uppercase_six_digits(value, expected):
    assert validate_hex_value(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "#",
        "#12",          # too short
        "#1234",        # 4 digits is not a hex color
        "#12345",
        "#1234567",     # too long
        "#GGGGGG",      # not hex digits
        "sage green",
        "rgb(1,2,3)",
    ],
)
def test_rejected_forms_raise(value):
    with pytest.raises(ValueError):
        validate_hex_value(value)


@pytest.mark.parametrize("value", [None, 123, ["#FFFFFF"], b"#FFFFFF"])
def test_non_strings_raise_rather_than_crash(value):
    # the model's tool input is untyped JSON, so a number can arrive here
    with pytest.raises(ValueError):
        validate_hex_value(value)


def test_the_error_names_the_offending_value(value="not a color"):
    with pytest.raises(ValueError, match="not a hex color"):
        validate_hex_value(value)


# ------------------------------------------------------------------ hex -> rgb

@pytest.mark.parametrize(
    "value, expected",
    [
        ("#000000", (0.0, 0.0, 0.0)),
        ("#FFFFFF", (1.0, 1.0, 1.0)),
        ("#FF0000", (1.0, 0.0, 0.0)),
        ("#00FF00", (0.0, 1.0, 0.0)),
        ("#0000FF", (0.0, 0.0, 1.0)),
    ],
)
def test_hex_to_rgb_is_channels_scaled_to_zero_one(value, expected):
    assert hex_to_rgb(value) == pytest.approx(expected)


def test_hex_to_rgb_normalizes_first(): 
    assert hex_to_rgb("fff") == hex_to_rgb("#FFFFFF")


# ------------------------------------------------------------------ rgb -> xyz

def test_white_maps_to_the_d65_reference_white():
    # the whole Lab chain is anchored to this point; if it drifts, L* for white
    # stops being 100 and every distance shifts
    assert rgb_to_xyz((1.0, 1.0, 1.0)) == pytest.approx((0.95047, 1.0, 1.08883), abs=1e-4)


def test_black_maps_to_the_origin():
    assert rgb_to_xyz((0.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0, 0.0))


def test_y_is_luminance_so_green_outweighs_blue():
    # the 0.7152 / 0.0722 coefficients are what make this true
    assert rgb_to_xyz((0, 1, 0))[1] > rgb_to_xyz((0, 0, 1))[1]


# ------------------------------------------------------------------ xyz -> lab

def test_reference_white_is_lightness_one_hundred_and_neutral():
    L, a, b = xyz_to_lab((0.95047, 1.0, 1.08883))
    assert L == pytest.approx(100.0, abs=1e-6)
    assert (a, b) == pytest.approx((0.0, 0.0), abs=1e-6)


def test_the_linear_branch_handles_very_dark_values():
    # below 216/24389 the cube root is replaced by a line; a near-black must
    # still come out with a small positive L rather than a nan
    L, _, _ = xyz_to_lab((0.0001, 0.0001, 0.0001))
    assert 0 < L < 1


# ------------------------------------------------------------------ lab -> lch

def test_chroma_is_the_distance_from_the_neutral_axis():
    _, chroma, _ = lab_to_lch((50.0, 3.0, 4.0))
    assert chroma == pytest.approx(5.0)


def test_hue_is_reported_in_degrees_zero_to_360():
    _, _, hue = lab_to_lch((50.0, 0.0, -1.0))
    assert hue == pytest.approx(270.0)


def test_lightness_passes_through_untouched():
    assert lab_to_lch((42.0, 1.0, 2.0))[0] == 42.0


def test_three_lightnesses_of_one_colour_share_hue_and_chroma():
    # the shadow/highlight case from the docstring: only L should move
    base = (30.0, 20.0, -10.0)
    _, c1, h1 = lab_to_lch(base)
    _, c2, h2 = lab_to_lch((70.0, 20.0, -10.0))
    assert (c1, h1) == pytest.approx((c2, h2))


# -------------------------------------------------------------------- distance

def test_a_colour_is_zero_distance_from_itself():
    assert distance("#B5C29A", "#B5C29A") == pytest.approx(0.0, abs=1e-9)


def test_distance_is_symmetric():
    assert distance("#B5C29A", "#E4A8C0") == pytest.approx(distance("#E4A8C0", "#B5C29A"))


def test_distance_is_never_negative():
    assert distance("#000000", "#FFFFFF") > 0


def test_distance_normalizes_its_inputs():
    assert distance("b5c29a", "#B5C29A") == pytest.approx(0.0, abs=1e-9)


def test_a_barely_different_colour_scores_under_one():
    # "under 1: indistinguishable", per the docstring
    assert distance("#FF0000", "#FE0000") < 1.0


def test_opposite_colours_score_far_over_twenty():
    assert distance("#FF0000", "#00FF00") > 20.0


def test_ciede2000_is_not_just_euclidean_lab():
    # if these ever agree, the correction terms have been lost
    red, green = hex_to_lab("#FF0000"), hex_to_lab("#00FF00")
    assert color_distance(red, green) != pytest.approx(raw_distance(red, green))


def test_raw_distance_is_plain_pythagoras():
    assert raw_distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == pytest.approx(5.0)


def test_two_greys_do_not_divide_by_zero():
    # both chromas are 0, which is the branch guarded by `if c_bar else 0.5`
    assert distance("#808080", "#7F7F7F") == pytest.approx(0.0, abs=0.5)


def test_black_against_black_is_zero_not_nan():
    result = distance("#000000", "#000000")
    assert result == result  # nan fails this
    assert result == pytest.approx(0.0)


# --------------------------------------------------------------- score_garment

def test_a_garment_scores_on_its_closest_colour():
    # a garment carries shadow and highlight codes; the best one represents it
    assert score_garment("#FF0000", ["#00FF00", "#FE0000"]) == pytest.approx(
        distance("#FF0000", "#FE0000")
    )


def test_a_single_colour_garment_scores_that_colour():
    assert score_garment("#FF0000", ["#DD2222"]) == pytest.approx(distance("#FF0000", "#DD2222"))


def test_adding_a_worse_colour_never_worsens_the_score():
    one = score_garment("#FF0000", ["#DD2222"])
    two = score_garment("#FF0000", ["#DD2222", "#00FF00"])
    assert two == pytest.approx(one)


def test_a_garment_with_no_colours_raises_rather_than_scoring():
    # min() of an empty sequence; extract.run is what prevents this reaching here
    with pytest.raises(ValueError):
        score_garment("#FF0000", [])


# --------------------------------------------------------------------- hue_gap

def test_hue_gap_wraps_around_the_wheel():
    # the docstring's example: near-0 and near-360 are close, not 340 apart
    assert hue_gap("#FF0000", "#FF0033") < 30


def test_hue_gap_of_a_colour_with_itself_is_zero():
    assert hue_gap("#B5C29A", "#B5C29A") == pytest.approx(0.0)


def test_hue_gap_never_exceeds_180():
    for other in ["#FF0000", "#00FF00", "#0000FF", "#B5C29A", "#E4A8C0"]:
        assert 0 <= hue_gap("#FF0000", other) <= 180


def test_hue_gap_is_symmetric():
    assert hue_gap("#B5C29A", "#E4A8C0") == pytest.approx(hue_gap("#E4A8C0", "#B5C29A"))
