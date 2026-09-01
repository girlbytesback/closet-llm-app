# Color Distance Formula Eval — CIE76 vs. CIEDE2000

**What this measures:** the app has to decide *how far apart* two colors are, and
there's more than one formula for that. This eval compares two of them —
**CIE76** (the simple one: straight-line distance in Lab space) and **CIEDE2000**
(the modern one, with corrections for how human vision actually works) — over the
same 48 garment errors, to decide which the project should use.

**Important:** this eval does **not** try to prove one formula is "more correct."
There's no perceptual ground truth here to check against. What it *can* show is
**where the two formulas disagree**, and whether those disagreements line up with
CIE76's known weak spots. That's the honest scope.

Sample: **48 garments.**

---

## TL;DR

- **You can't compare the two by raw score.** CIE76 runs about **1.44× larger**
  than CIEDE2000 on the same data (averages **14.2** vs **9.9**), so a fixed
  pass/fail threshold would punish CIE76 just for using a bigger ruler. The fair
  comparison is **ranking** — do the two formulas agree on *which* garments are
  the worst?
- **Mostly yes, but not always.** The two rankings agree strongly overall
  (**Spearman ρ = 0.93**), and **8/48** garments don't move at all. But **40/48**
  shift by at least one place, with a mean shift of **3.6** and a max of **18**.
- **The disagreements are the interesting part**, and they cluster on exactly the
  colors CIE76 is known to mishandle. The headline case is **GARMENT_33**, a dark
  navy: CIE76 calls it the **single worst** error (ΔE 45.9, rank #1); CIEDE2000
  rates it only **12th** worst (ΔE 14.8). CIE76 massively over-penalizes it.
- **Conclusion:** use **CIEDE2000**. Not because it scored "better" (that's not a
  meaningful claim without ground truth), but because its corrections specifically
  target the dark/blue over-penalization CIE76 shows here, and its ordering doesn't
  swing wildly on those cases.

---

## Why ranking, not pass rates

It's tempting to run both formulas at, say, ΔE ≤ 10 and compare how many pass. That
would be **misleading**. CIE76 and CIEDE2000 aren't on the same scale — CIE76's
numbers are ~1.44× bigger here by construction. Judging them against one shared
threshold would just measure "which formula produces smaller numbers," not "which
formula orders the errors more sensibly."

So instead the eval ranks all 48 garments worst-to-best under each formula and asks:
**do the two orderings agree?** Rank is scale-independent — it doesn't care that one
ruler reads bigger — so it isolates the thing we actually care about: whether the
formulas *disagree about which garments are the problem ones*.

---

## What the comparison shows

**Broad agreement.** Spearman ρ = 0.93 is high. The extremes especially line up:
the worst reds/pinks stay near the top under both formulas, and the near-blacks
(GARMENT_47, 28, 55) stay at the bottom under both. For most garments, it wouldn't
matter which formula you picked.

**Localized disagreement.** The picture breaks down in specific places, and those
places are telling:

| Garment | CIE76 rank | CIEDE2000 rank | Shift | What it is |
|---|---|---|---|---|
| GARMENT_13 | #11 (ΔE 19.6) | #29 (ΔE 7.5) | **−18** | CIE76 flags it as a top-tier error; CIEDE2000 says middling |
| GARMENT_14 | #25 (ΔE 12.1) | #37 (ΔE 5.8) | **−12** | same pattern, smaller |
| GARMENT_33 | **#1** (ΔE 45.9) | #12 (ΔE 14.8) | **−11** | dark navy — CIE76's "worst error," CIEDE2000 disagrees hard |
| GARMENT_26 | #34 (ΔE 9.0) | #43 (ΔE 4.5) | **−9** | CIE76 over-weights it |
| GARMENT_49 | #33 (ΔE 9.1) | #25 (ΔE 8.1) | **+8** | the reverse — CIEDE2000 weights it *more* |

The large negative shifts (CIE76 ranks something much worse than CIEDE2000 does)
are the signature of CIE76's core flaw: it treats every direction in Lab space as
equally significant, so it **over-penalizes differences in dark and blue regions**
that human eyes barely notice. GARMENT_33 (a dark navy) is the textbook example —
CIE76's straight-line distance balloons to 45.9 while CIEDE2000's perceptual
correction pulls it back to a much more reasonable 14.8.

---

## Conclusion

Use **CIEDE2000** as the project's distance metric.

The justification is *not* "it passed more" or "it's more accurate" — this eval
can't establish either without perceptual ground truth. The justification is:

1. The two formulas genuinely disagree on ~40 of 48 garments, so the choice matters.
2. The disagreements concentrate on dark/blue colors, which is precisely where
   CIE76 is known to overstate differences.
3. CIEDE2000's whole design is the correction for that failure mode.

So CIEDE2000 is the better-motivated choice for a color-matching app, and this eval
documents *why* rather than asserting it.

---

## Full comparison (sorted by CIEDE2000, worst to best)

- **CIE76** / **rank** — straight-line Lab distance and its worst-to-best position.
- **ΔE2000** / **rank** — perceptual distance and its position.
- **moved** — how many places the garment shifts going from CIE76 to CIEDE2000.
  Big numbers = the two formulas disagree about that garment.

| Garment | CIE76 | rank | ΔE2000 | rank | moved |
|---|---:|:---:|---:|:---:|:---:|
| GARMENT_29 | 40.35 | 2 | 24.43 | 1 | +1 |
| GARMENT_39 | 26.86 | 3 | 24.12 | 2 | +1 |
| GARMENT_1 | 21.47 | 9 | 19.34 | 3 | +6 |
| GARMENT_18 | 21.60 | 7 | 19.32 | 4 | +3 |
| GARMENT_21 | 23.42 | 5 | 18.39 | 5 | 0 |
| GARMENT_17 | 22.78 | 6 | 17.43 | 6 | 0 |
| GARMENT_12 | 25.47 | 4 | 17.34 | 7 | −3 |
| GARMENT_36 | 17.46 | 15 | 15.69 | 8 | +7 |
| GARMENT_5 | 20.94 | 10 | 15.52 | 9 | +1 |
| GARMENT_41 | 17.17 | 16 | 15.45 | 10 | +6 |
| GARMENT_50 | 18.08 | 14 | 15.07 | 11 | +3 |
| GARMENT_33 | 45.92 | 1 | 14.82 | 12 | **−11** |
| GARMENT_51 | 15.16 | 18 | 14.46 | 13 | +5 |
| GARMENT_19 | 21.58 | 8 | 12.15 | 14 | −6 |
| GARMENT_22 | 15.63 | 17 | 11.03 | 15 | +2 |
| GARMENT_16 | 18.65 | 12 | 10.47 | 16 | −4 |
| GARMENT_54 | 13.90 | 20 | 9.97 | 17 | +3 |
| GARMENT_25 | 18.21 | 13 | 9.94 | 18 | −5 |
| GARMENT_10 | 14.37 | 19 | 9.12 | 19 | 0 |
| GARMENT_27 | 12.45 | 23 | 8.96 | 20 | +3 |
| GARMENT_23 | 13.18 | 22 | 8.79 | 21 | +1 |
| GARMENT_48 | 13.26 | 21 | 8.76 | 22 | −1 |
| GARMENT_42 | 10.36 | 28 | 8.46 | 23 | +5 |
| GARMENT_34 | 9.64 | 31 | 8.16 | 24 | +7 |
| GARMENT_49 | 9.11 | 33 | 8.08 | 25 | **+8** |
| GARMENT_2 | 12.10 | 24 | 7.99 | 26 | −2 |
| GARMENT_15 | 10.70 | 27 | 7.97 | 27 | 0 |
| GARMENT_53 | 8.64 | 36 | 7.80 | 28 | **+8** |
| GARMENT_13 | 19.57 | 11 | 7.49 | 29 | **−18** |
| GARMENT_31 | 10.33 | 29 | 7.42 | 30 | −1 |
| GARMENT_45 | 11.39 | 26 | 7.42 | 31 | −5 |
| GARMENT_4 | 10.21 | 30 | 6.60 | 32 | −2 |
| GARMENT_40 | 8.14 | 38 | 6.57 | 33 | +5 |
| GARMENT_38 | 8.63 | 37 | 6.26 | 34 | +3 |
| GARMENT_20 | 9.55 | 32 | 5.77 | 35 | −3 |
| GARMENT_9 | 8.70 | 35 | 5.76 | 36 | −1 |
| GARMENT_14 | 12.05 | 25 | 5.75 | 37 | **−12** |
| GARMENT_37 | 7.21 | 40 | 5.59 | 38 | +2 |
| GARMENT_52 | 7.79 | 39 | 5.51 | 39 | 0 |
| GARMENT_32 | 5.35 | 45 | 4.86 | 40 | +5 |
| GARMENT_3 | 5.93 | 41 | 4.71 | 41 | 0 |
| GARMENT_24 | 5.87 | 42 | 4.69 | 42 | 0 |
| GARMENT_26 | 9.01 | 34 | 4.51 | 43 | **−9** |
| GARMENT_46 | 5.59 | 43 | 4.20 | 44 | −1 |
| GARMENT_8 | 5.59 | 44 | 4.00 | 45 | −1 |
| GARMENT_55 | 3.91 | 47 | 3.21 | 46 | +1 |
| GARMENT_28 | 4.04 | 46 | 2.42 | 47 | −1 |
| GARMENT_47 | 2.10 | 48 | 1.41 | 48 | 0 |

*Averages: CIE76 = 14.2, CIEDE2000 = 9.9 (1.44× larger). Ranking agreement:
Spearman ρ = 0.93. 8/48 unchanged, mean absolute shift 3.6 places, max 18.*