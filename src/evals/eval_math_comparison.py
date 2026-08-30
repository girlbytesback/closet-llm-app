from closetllm.config import garment_hex_colors
from closetllm.color import distance, raw_distance, hex_to_lab
from closetllm.extract import load_data

from evals.answer_key import answer_key

# EVALUATES WHICH FORMULA IS THE BETTER ONE TO USE


# Load the model's guesses from clothes.json — same as your extraction eval
# Walk the answer key, skip blanks — same loop you already have
# For each garment, compute two distances instead of one ← the only new part
# Rank the garments under each formula
# Print the report

def compare_model_formula(answer_key, model_colors):
    results = []

    for garment_file_name, actual_hex in answer_key.items():
        if not actual_hex:
            continue #to be compared later bc blank rn
        if garment_file_name not in model_colors:
            print(f"{garment_file_name} is not found in clothes.json")
            continue
        model_hex = model_colors[garment_file_name][0]
        cie76_difference = raw_distance(hex_to_lab(actual_hex), hex_to_lab(model_hex))
        cie2000_difference = distance(actual_hex, model_hex)
        results.append((
            garment_file_name, 
            actual_hex, 
            model_hex, 
            cie76_difference,
            cie2000_difference
        ))

    return results

def rank_map(results, score_index):
    """ garment -> position when sorted by worst formula."""
    ordered = sorted(results, key=lambda row: row[score_index], reverse=True)
    return {row[0]: position for position, row in enumerate(ordered, start=1)}

def generate_eval_report(results):
    if not results:
        print("answer key doesnt exist")
        return

    cie76_rank = rank_map(results, 3)
    cie2000_rank = rank_map(results, 4)
    
    cie76_average = sum(row[3] for row in results) / len(results)
    cie2000_average = sum(row[4] for row in results) / len(results)

    cie76_worst = max(results, key=lambda row: row[3])
    cie2000_worst = max(results, key=lambda row: row[4])
 
    print(f"\nmeasured:    {len(results)} garments")
    print(f"CIE76 averages {cie76_average:.1f}, CIEDE2000 averages "
          f"{cie2000_average:.1f} ({cie76_average / cie2000_average:.2f}x bigger)")

    print(f"\nworst miss per formula:")
    print(f"  ΔCIE76:     {cie76_worst[0]}  gap {cie76_worst[3]:.1f}")
    print(f"  ΔCIEDE2000: {cie2000_worst[0]}  gap {cie2000_worst[4]:.1f}")

    print(f"\n{'garment':16} {'CIE76':>8} {'rank':>5} {'ΔE2000':>8} {'rank':>5} {'moved':>7}")
    for row in sorted(results, key=lambda row: row[4], reverse=True):
        name = row[0]
        moved = cie76_rank[name] - cie2000_rank[name]
        marker = "" if moved == 0 else "  <--"
        print(f"{name:16} {row[3]:8.2f} {cie76_rank[name]:5} "
              f"{row[4]:8.2f} {cie2000_rank[name]:5} {moved:+7}{marker}")
 
    movers = [row[0] for row in results if cie76_rank[row[0]] != cie2000_rank[row[0]]]
    print(f"\n{len(movers)}/{len(results)} garments changed position between formulas.")
    if movers:
        biggest = max(results, key=lambda row: abs(cie76_rank[row[0]] - cie2000_rank[row[0]]))
        shift = abs(cie76_rank[biggest[0]] - cie2000_rank[biggest[0]])
        print(f"biggest disagreement: {biggest[0]} moved {shift} places "
              f"(measured {biggest[1]}, model said {biggest[2]})")
    
    


if __name__ == "__main__":
    model_colors = load_data(garment_hex_colors)   # the model's guesses
    results = compare_model_formula(answer_key, model_colors)
    generate_eval_report(results)
