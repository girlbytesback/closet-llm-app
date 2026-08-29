import csv
import pytest
from pathlib import Path
from closetllm.color import color_distance, validate_hex_value, hex_to_lab

DATA = Path(__file__).parent / "ciede2000testdata.txt"

# https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/

# test data input normalization
def test_valid_space_hex_value():
    assert validate_hex_value("#3471AE   ") == "#3471AE"
    assert validate_hex_value("#3471AE") == "#3471AE"
    assert validate_hex_value("  #3471AE   ") == "#3471AE"

def test_invalid_space_hex_value():
    with pytest.raises(ValueError):
        validate_hex_value("  ")       

def test_hex_value_expansion():
    assert validate_hex_value("#012") == '#001122'

def load_test_calculations():
    pairs = []
    with open(DATA) as file:
        for row in file:
            if not row.strip():
                continue
            L1, a1, b1, L2, a2, b2, difference = map(float, row.split())
            pairs.append(((L1, a1, b1), (L2, a2, b2), difference))
    return pairs

def test_lab_calculation():
    for lab1, lab2, difference in load_test_calculations():
        actual = color_distance(lab1, lab2)
        assert abs(actual - difference) < 0.0001, (
            f"color_distance{lab1, lab2} = {actual:.4f}, expected {difference:.4f}"
        )

# HEX -> LAB!!!!!!!
# we know if L == 100, a = 0, b = 0 will be WHITE

def test_LAB_calc_with_white():
    L, a, b = hex_to_lab("#FFFFFF")
    assert L == pytest.approx(100.0, abs=0.01)
    assert a == pytest.approx(0.0, abs=0.01)
    assert b == pytest.approx(0.0, abs=0.01)

# we know if L == 0, a = 0, b = 0 will be BLACK
def test_LAB_calc_with_white():
    L, a, b = hex_to_lab("#000000")
    assert L == pytest.approx(0.0, abs=0.01)
    assert a == pytest.approx(0.0, abs=0.01)
    assert b == pytest.approx(0.0, abs=0.01)

# we know if L == 0, a = 0, b = 0 will be BLACK
def test_LAB_calc_with_gray():
    black = hex_to_lab("#000000")[0]
    grey  = hex_to_lab("#808080")[0]
    white = hex_to_lab("#FFFFFF")[0]
    assert black < grey < white