"""The eval harnesses' pure parts, on synthetic data.

The numbers the README quotes are pinned separately, in the regression suite —
here the answer key is made up, so the arithmetic can be checked by hand.
"""

import pytest

from closetllm.color import distance, hex_to_lab, raw_distance
from evals.eval_extraction import compare_model_truth
from evals.eval_extraction import generate_eval_report as extraction_report
from evals.eval_math_comparison import compare_model_formula, rank_map


KEY = {"a.jpg": "#B5C29A", "b.jpg": "#E4A8C0"}
GUESSES = {"a.jpg": ["#B7C39B"], "b.jpg": ["#DFA3BC"]}


# ----------------------------------------------------------- compare_model_truth

def test_one_row_per_graded_garment():
    rows = compare_model_truth(KEY, GUESSES)
    assert [row[0] for row in rows] == ["a.jpg", "b.jpg"]


def test_a_row_carries_the_measured_colour_the_guess_and_the_gap():
    name, measured, guessed, gap = compare_model_truth(KEY, GUESSES)[0]

    assert (name, measured, guessed) == ("a.jpg", "#B5C29A", "#B7C39B")
    assert gap == pytest.approx(distance("#B5C29A", "#B7C39B"))


def test_a_blank_answer_key_entry_is_skipped_not_scored_as_zero():
    # unmeasured garments would otherwise all score a perfect 0 and inflate the
    # pass rate
    rows = compare_model_truth({**KEY, "c.jpg": ""}, {**GUESSES, "c.jpg": ["#000000"]})
    assert [row[0] for row in rows] == ["a.jpg", "b.jpg"]


def test_a_garment_the_model_never_saw_is_reported_and_skipped(capsys):
    rows = compare_model_truth({**KEY, "missing.jpg": "#123456"}, GUESSES)

    assert len(rows) == 2
    assert "missing.jpg is not found in clothes.json" in capsys.readouterr().out


def test_only_the_first_colour_of_a_garment_is_graded():
    # the answer key holds one measured colour, so the comparison uses the
    # model's primary
    rows = compare_model_truth({"a.jpg": "#B5C29A"}, {"a.jpg": ["#B7C39B", "#000000"]})
    assert rows[0][3] == pytest.approx(distance("#B5C29A", "#B7C39B"))


def test_an_empty_answer_key_grades_nothing():
    assert compare_model_truth({}, GUESSES) == []


def test_the_report_says_so_when_there_is_nothing_to_grade(capsys):
    extraction_report([])
    assert "answer key doesnt exist" in capsys.readouterr().out


def test_the_report_prints_the_pass_rate_and_the_worst_miss(capsys):
    extraction_report(compare_model_truth(KEY, GUESSES))
    out = capsys.readouterr().out

    assert "measured:    2 garments" in out
    assert "pass rate:" in out
    assert "worst miss:" in out


def test_the_report_marks_a_wild_guess_as_a_failure(capsys):
    extraction_report(compare_model_truth({"a.jpg": "#B5C29A"}, {"a.jpg": ["#FF0000"]}))
    assert "[FAIL]" in capsys.readouterr().out


def test_the_report_marks_a_close_guess_as_a_pass(capsys):
    extraction_report(compare_model_truth({"a.jpg": "#B5C29A"}, {"a.jpg": ["#B5C29B"]}))
    assert "[PASS]" in capsys.readouterr().out


# --------------------------------------------------------- compare_model_formula

def test_the_formula_comparison_scores_both_metrics():
    name, measured, guessed, cie76, cie2000 = compare_model_formula(KEY, GUESSES)[0]

    assert cie76 == pytest.approx(raw_distance(hex_to_lab(measured), hex_to_lab(guessed)))
    assert cie2000 == pytest.approx(distance(measured, guessed))


def test_cie76_reads_larger_than_ciede2000_on_real_garments():
    # this is the finding the comparison exists to show
    for _, _, _, cie76, cie2000 in compare_model_formula(KEY, GUESSES):
        assert cie76 > cie2000


def test_rank_map_numbers_the_worst_garment_first():
    rows = [("good", "", "", 1.0, 1.0), ("bad", "", "", 9.0, 9.0)]
    assert rank_map(rows, 3) == {"bad": 1, "good": 2}


def test_rank_map_covers_every_row():
    rows = compare_model_formula(KEY, GUESSES)
    assert set(rank_map(rows, 4)) == {row[0] for row in rows}
    assert sorted(rank_map(rows, 4).values()) == [1, 2]
