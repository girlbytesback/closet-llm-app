import csv
from pathlib import Path
from closetllm.color import color_distance

DATA = Path(__file__).parent / "ciede2000testdata.txt"

# https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/

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