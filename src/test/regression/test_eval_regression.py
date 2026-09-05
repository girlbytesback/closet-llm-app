"""The numbers the README publishes, recomputed from what's committed.

    only 9/48 extractions land within ΔE <= 5 (32/48 within ΔE <= 10), and the
    misses aren't random — the model reads colors lighter (+7.3 L*) and more
    saturated (+5.4 chroma) than reality, worst on dark saturated reds.

These are the project's headline claim. They depend on three committed things:
the hand-measured answer key, data/clothes.json, and the distance function. If
any of them moves, the README is wrong until it's updated — that's what this
file is for. No model call happens here; the guesses are already on disk.
"""

import pytest

from closetllm.color import hex_to_lab, lab_to_lch
from closetllm.config import garment_hex_colors
from closetllm.extract import load_data
from evals.answer_key import answer_key
from evals.eval_extraction import THRESHOLD, compare_model_truth
from evals.eval_math_comparison import compare_model_formula


@pytest.fixture(scope="module")
def graded():
    """The real answer key scored against the real committed extractions."""
    rows = compare_model_truth(answer_key, load_data(garment_hex_colors))
    if not rows:
        pytest.skip("data/clothes.json is empty — run `closetllm clothes` first")
    return rows


def test_the_answer_key_covers_forty_eight_garments(graded):
    assert len(graded) == 48


def test_nine_extractions_land_within_delta_e_five(graded):
    assert sum(1 for row in graded if row[3] <= 5) == 9


def test_thirty_two_extractions_land_within_delta_e_ten(graded):
    assert sum(1 for row in graded if row[3] <= 10) == 32


def test_the_average_gap_is_just_under_ten(graded):
    average = sum(row[3] for row in graded) / len(graded)
    assert average == pytest.approx(9.85, abs=0.01)


def test_the_model_reads_colours_lighter_by_seven_l_star(graded):
    bias = [hex_to_lab(guess)[0] - hex_to_lab(measured)[0] for _, measured, guess, _ in graded]
    assert sum(bias) / len(bias) == pytest.approx(7.3, abs=0.05)


def test_the_model_reads_colours_more_saturated_by_five_chroma(graded):
    def chroma(hex_value):
        return lab_to_lch(hex_to_lab(hex_value))[1]

    bias = [chroma(guess) - chroma(measured) for _, measured, guess, _ in graded]
    assert sum(bias) / len(bias) == pytest.approx(5.36, abs=0.05)


def test_the_bias_is_directional_not_noise(graded):
    # the claim isn't "the model is inaccurate", it's "the model is inaccurate
    # in one direction" — most garments must be read lighter, not just the mean
    lighter = sum(
        1 for _, measured, guess, _ in graded if hex_to_lab(guess)[0] > hex_to_lab(measured)[0]
    )
    assert lighter > len(graded) * 0.7


def test_the_worst_miss_is_still_a_dark_saturated_red(graded):
    name, measured, _, gap = max(graded, key=lambda row: row[3])

    assert name == "GARMENT_29.jpg"
    assert measured == "#D2305B"
    assert gap == pytest.approx(24.43, abs=0.01)


def test_the_pass_threshold_the_report_prints_is_still_five():
    assert THRESHOLD == 5.0


def test_cie76_reads_larger_than_ciede2000_across_the_whole_set():
    # the conclusion of eval_math_comparison: the correction terms pull the
    # numbers down, so a cutoff tuned on one formula is wrong for the other
    rows = compare_model_formula(answer_key, load_data(garment_hex_colors))
    if not rows:
        pytest.skip("data/clothes.json is empty")

    cie76 = sum(row[3] for row in rows) / len(rows)
    cie2000 = sum(row[4] for row in rows) / len(rows)

    assert cie76 > cie2000


def test_every_answer_key_entry_is_a_usable_hex_code():
    from closetllm.color import validate_hex_value

    for name, measured in answer_key.items():
        assert measured, f"{name} has no measured colour"
        assert validate_hex_value(measured) == measured.upper()
