# 🖍️ Color Distance Formula Eval — CIE76 vs. CIEDE2000 🖌️

**What this measures:** 

After the model extracts a color from the photo, we want to measure if the color matches the color palettes its being compared against. Two formulas are used to measure this and this doc evaluates the results.


#####  **CIE76 formula**: standard 3D Euclidean distance formula:
 
 $$d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2 + (z_2 - z_1)^2}$$

 ##### **CIE2000 formula**: mathematical formula calculating the perceived difference between two colors, weighted to match how the human eye sees color

$$ \Delta E_{00} = \sqrt{\left(\frac{\Delta L'}{k_L S_L}\right)^2 + \left(\frac{\Delta C'}{k_C S_C}\right)^2 + \left(\frac{\Delta H'}{k_H S_H}\right)^2 + R_T \left(\frac{\Delta C'}{k_C S_C}\right) \left(\frac{\Delta H'}{k_H S_H}\right)} $$

#### Variable Breakdown

*   **$\Delta E_{00}$**: The final calculated perceptual color difference score.

*   **$\Delta L'$**: The difference in modified **Lightness** between the two colors.
*   **$\Delta C'$**: The difference in modified **Chroma** (saturation) between the two colors.

*   **$\Delta H'$**: The difference in modified **Hue** (color family) between the two colors.

*   **$S_L, S_C, S_H$**: The **weighting functions** for Lightness, Chroma, and Hue. These adjust the formula's sensitivity depending on how bright, saturated, or neutral the color is.

*   **$k_L, k_C, k_H$**: Parametric **scaling factors** usually determined by the specific industry or viewing conditions. In standard applications, they are all set to a default value of **$1$** ($1:1:1$).

*   **$R_T$**: The **rotation term**. A correction factor specifically designed to handle calculation anomalies in the blue-purple region (around a $275^\circ$ hue angle), where human vision behaves non-linearly.

<small>* formula created by international committee of color scientists working under the CIE (International Commission on Illumination)</small>

This eval does **NOT** try to prove one formula is "more correct."
There's no perceptual ground truth here to check against. What it *does* show is
**where the two formulas disagree**, and whether those disagreements line up with CIE76's known weak spots

### SAMPLE SIZE: 48 garments


## TLDR !! 💭

- **You can't compare the two by raw score.** CIE76 runs about **1.44× larger**
  than CIEDE2000 on the same data (averages **14.2** vs **9.9**), so a fixed
  pass/fail threshold would punish CIE76 just for using a bigger ruler. 

- **The fair comparison is **ranking** — do the two formulas agree on *which* garments are
  the worst?** The two rankings agree strongly overall, and **8/48** garments don't move at all. But **40/48**
  shift by at least one place, with a mean shift of **3.6** and a max of **18**.

- **The disagreements align with known errors of CIE76**,  they cluster on exactly the colors CIE76 is known to mishandle. The most prominent case is `GARMENT_33`, a dark
  navy: CIE76 calls it the **single worst** error (ΔE 45.9, rank #1); CIEDE2000
  rates it only **12th** worst (ΔE 14.8). CIE76 massively over-penalizes it.

- **Conclusion:** use **CIEDE2000**. Not because it scored "better" (that's not a
  meaningful claim without ground truth), but because its corrections specifically
  target the dark/blue over-penalization CIE76 shows here, and its ordering doesn't
  swing wildly on those cases.


## Why evalute by ranking?

It's tempting to run both formulas at the same threshold and compare how many pass, but this is **misleading** as CIE76 and CIEDE2000 do not use the same scale (CIE76's numbers are ~1.44× bigger here by construction. Judging them against one shared
threshold would just measure *"which formula produces smaller numbers," NOT "which
formula orders the errors more sensibly."*

So instead the eval ranks all 48 garments worst-to-best under each formula and asks:
**do the two orderings agree?** Rank is scale-independent, so it isolates whether the
formulas disagree about which garments are incorrect.


## Eval findings:

**The two formulas mostly agree.** In order to compare CIE76 and CIEDE2000 fairly, all 48 garments are ranked from worst-to-best under each formula and the results produced are compared side by side.


**But they disagree in specific spots — and those spots are the interesting
part.** The orderings come apart in a few places, and it's not random which ones:

| Garment | Measured | Model | CIE76 rank | CIEDE2000 rank | Shift | What it is |
|---|:---:|:---:|---|---|---|---|
| GARMENT_13 | ![](https://placehold.co/20x20/BBB97F/BBB97F.png) | ![](https://placehold.co/20x20/B7C464/B7C464.png) | #11 (ΔE 19.6) | #29 (ΔE 7.5) | **−18** | CIE76 flags it as a top-tier error; CIEDE2000 says middling |
| GARMENT_14 | ![](https://placehold.co/20x20/D2DFA3/D2DFA3.png) | ![](https://placehold.co/20x20/B9D183/B9D183.png) | #25 (ΔE 12.1) | #37 (ΔE 5.8) | **−12** | same pattern, smaller |
| GARMENT_33 | ![](https://placehold.co/20x20/17224E/17224E.png) | ![](https://placehold.co/20x20/2A32A8/2A32A8.png) | **#1** (ΔE 45.9) | #12 (ΔE 14.8) | **−11** | dark navy — CIE76's "worst error," CIEDE2000 disagrees hard |
| GARMENT_26 | ![](https://placehold.co/20x20/9D6687/9D6687.png) | ![](https://placehold.co/20x20/A85C7E/A85C7E.png) | #34 (ΔE 9.0) | #43 (ΔE 4.5) | **−9** | CIE76 over-weights it |
| GARMENT_49 | ![](https://placehold.co/20x20/B8DCDE/B8DCDE.png) | ![](https://placehold.co/20x20/B9D6E8/B9D6E8.png) | #33 (ΔE 9.1) | #25 (ΔE 8.1) | **+8** | the reverse — CIEDE2000 weights it *more* |

The <i> "shift" </i> column shows the numerical inconsistency between the two formulas' rankings. `GARMENT_13` shows how CIE76 and CIE2000's numbers do not agree that the color the model guessed is accurate.


The large negative shifts (when CIE76 ranks something much worse than CIEDE2000 does), it **over-penalizes differences in dark and blue regions**
that human eyes barely notice. For instance, `GARMENT_33` (a dark navy) calculates a distance of 45.9 while CIEDE2000 captures the similarity and produces a reasonable score of 14.8.

## Conclusion

Use **CIEDE2000** as the project's distance formula.

1. The two formulas genuinely disagree on ~40 of 48 garments, so the choice matters.
2. The disagreements concentrate on dark/blue colors, which is precisely where
   CIE76 is known to overstate differences.
3. CIEDE2000's whole design is the correction for that failure mode.

So CIEDE2000 is the better-motivated choice for a color-matching app, and this eval
documents *why* rather than asserting it.



## Full comparison (sorted by CIEDE2000, from BEST to)

- **Measured / Model** — the hand-measured truth color and what the model reported.
- **CIE76** / **rank** — straight-line Lab distance and its worst-to-best position.
- **ΔE2000** / **rank** — perceptual distance and its position.
- **moved** — how many places the garment shifts going from CIE76 to CIEDE2000.

| Garment | Measured | Model | CIE76 | rank | ΔE2000 | rank | moved |
|---|:---:|:---:|---:|:---:|---:|:---:|:---:|
| GARMENT_47 | ![](https://placehold.co/20x20/0B0A08/0B0A08.png) | ![](https://placehold.co/20x20/101010/101010.png) | 2.10 | 48 | 1.41 | 48 | 0 |
| GARMENT_28 | ![](https://placehold.co/20x20/D2305B/D2305B.png) | ![](https://placehold.co/20x20/CE2751/CE2751.png) | 4.04 | 46 | 2.42 | 47 | −1 |
| GARMENT_55 | ![](https://placehold.co/20x20/3D3432/3D3432.png) | ![](https://placehold.co/20x20/332E2E/332E2E.png) | 3.91 | 47 | 3.21 | 46 | +1 |
| GARMENT_8 | ![](https://placehold.co/20x20/91A193/91A193.png) | ![](https://placehold.co/20x20/94A891/94A891.png) | 5.59 | 44 | 4.00 | 45 | −1 |
| GARMENT_46 | ![](https://placehold.co/20x20/E2E3DE/E2E3DE.png) | ![](https://placehold.co/20x20/F5F0E8/F5F0E8.png) | 5.59 | 43 | 4.20 | 44 | −1 |
| GARMENT_26 | ![](https://placehold.co/20x20/9D6687/9D6687.png) | ![](https://placehold.co/20x20/A85C7E/A85C7E.png) | 9.01 | 34 | 4.51 | 43 | **−9** |
| GARMENT_24 | ![](https://placehold.co/20x20/B5AE84/B5AE84.png) | ![](https://placehold.co/20x20/C4B183/C4B183.png) | 5.87 | 42 | 4.69 | 42 | 0 |
| GARMENT_3 | ![](https://placehold.co/20x20/1E1E20/1E1E20.png) | ![](https://placehold.co/20x20/2A2724/2A2724.png) | 5.93 | 41 | 4.71 | 41 | 0 |
| GARMENT_32 | ![](https://placehold.co/20x20/313A46/313A46.png) | ![](https://placehold.co/20x20/2B3040/2B3040.png) | 5.35 | 45 | 4.86 | 40 | +5 |
| GARMENT_52 | ![](https://placehold.co/20x20/020200/020200.png) | ![](https://placehold.co/20x20/15161A/15161A.png) | 7.79 | 39 | 5.51 | 39 | 0 |
| GARMENT_37 | ![](https://placehold.co/20x20/3A3D3F/3A3D3F.png) | ![](https://placehold.co/20x20/2B3038/2B3038.png) | 7.21 | 40 | 5.59 | 38 | +2 |
| GARMENT_14 | ![](https://placehold.co/20x20/D2DFA3/D2DFA3.png) | ![](https://placehold.co/20x20/B9D183/B9D183.png) | 12.05 | 25 | 5.75 | 37 | **−12** |
| GARMENT_9 | ![](https://placehold.co/20x20/544D2C/544D2C.png) | ![](https://placehold.co/20x20/5C5A2C/5C5A2C.png) | 8.70 | 35 | 5.76 | 36 | −1 |
| GARMENT_20 | ![](https://placehold.co/20x20/751722/751722.png) | ![](https://placehold.co/20x20/8E1D33/8E1D33.png) | 9.55 | 32 | 5.77 | 35 | −3 |
| GARMENT_38 | ![](https://placehold.co/20x20/3D4048/3D4048.png) | ![](https://placehold.co/20x20/2A2E3A/2A2E3A.png) | 8.63 | 37 | 6.26 | 34 | +3 |
| GARMENT_40 | ![](https://placehold.co/20x20/7D869B/7D869B.png) | ![](https://placehold.co/20x20/8296B4/8296B4.png) | 8.14 | 38 | 6.57 | 33 | +5 |
| GARMENT_4 | ![](https://placehold.co/20x20/573F3B/573F3B.png) | ![](https://placehold.co/20x20/6B4238/6B4238.png) | 10.21 | 30 | 6.60 | 32 | −2 |
| GARMENT_45 | ![](https://placehold.co/20x20/D3D2CB/D3D2CB.png) | ![](https://placehold.co/20x20/F2F1EF/F2F1EF.png) | 11.39 | 26 | 7.42 | 31 | −5 |
| GARMENT_31 | ![](https://placehold.co/20x20/30303C/30303C.png) | ![](https://placehold.co/20x20/1E1E22/1E1E22.png) | 10.33 | 29 | 7.42 | 30 | −1 |
| GARMENT_13 | ![](https://placehold.co/20x20/BBB97F/BBB97F.png) | ![](https://placehold.co/20x20/B7C464/B7C464.png) | 19.57 | 11 | 7.49 | 29 | **−18** |
| GARMENT_53 | ![](https://placehold.co/20x20/606C6C/606C6C.png) | ![](https://placehold.co/20x20/455B5D/455B5D.png) | 8.64 | 36 | 7.80 | 28 | **+8** |
| GARMENT_15 | ![](https://placehold.co/20x20/273F3D/273F3D.png) | ![](https://placehold.co/20x20/1F4A3D/1F4A3D.png) | 10.70 | 27 | 7.97 | 27 | 0 |
| GARMENT_2 | ![](https://placehold.co/20x20/1B3671/1B3671.png) | ![](https://placehold.co/20x20/334F84/334F84.png) | 12.10 | 24 | 7.99 | 26 | −2 |
| GARMENT_49 | ![](https://placehold.co/20x20/B8DCDE/B8DCDE.png) | ![](https://placehold.co/20x20/B9D6E8/B9D6E8.png) | 9.11 | 33 | 8.08 | 25 | **+8** |
| GARMENT_34 | ![](https://placehold.co/20x20/C4C6C5/C4C6C5.png) | ![](https://placehold.co/20x20/B4C6D4/B4C6D4.png) | 9.64 | 31 | 8.16 | 24 | +7 |
| GARMENT_42 | ![](https://placehold.co/20x20/999174/999174.png) | ![](https://placehold.co/20x20/B6AC8C/B6AC8C.png) | 10.36 | 28 | 8.46 | 23 | +5 |
| GARMENT_48 | ![](https://placehold.co/20x20/CBC7BF/CBC7BF.png) | ![](https://placehold.co/20x20/F2EADA/F2EADA.png) | 13.26 | 21 | 8.76 | 22 | −1 |
| GARMENT_23 | ![](https://placehold.co/20x20/D1C6B0/D1C6B0.png) | ![](https://placehold.co/20x20/F2E9C8/F2E9C8.png) | 13.18 | 22 | 8.79 | 21 | +1 |
| GARMENT_27 | ![](https://placehold.co/20x20/BFA5BA/BFA5BA.png) | ![](https://placehold.co/20x20/E5C3D1/E5C3D1.png) | 12.45 | 23 | 8.96 | 20 | +3 |
| GARMENT_10 | ![](https://placehold.co/20x20/979C78/979C78.png) | ![](https://placehold.co/20x20/7C8A52/7C8A52.png) | 14.37 | 19 | 9.12 | 19 | 0 |
| GARMENT_25 | ![](https://placehold.co/20x20/4C1421/4C1421.png) | ![](https://placehold.co/20x20/7B1F35/7B1F35.png) | 18.21 | 13 | 9.94 | 18 | −5 |
| GARMENT_54 | ![](https://placehold.co/20x20/D7BDBA/D7BDBA.png) | ![](https://placehold.co/20x20/F7E4DA/F7E4DA.png) | 13.90 | 20 | 9.97 | 17 | +3 |
| GARMENT_16 | ![](https://placehold.co/20x20/9E3134/9E3134.png) | ![](https://placehold.co/20x20/C0402C/C0402C.png) | 18.65 | 12 | 10.47 | 16 | −4 |
| GARMENT_22 | ![](https://placehold.co/20x20/BDB1A3/BDB1A3.png) | ![](https://placehold.co/20x20/D6CBA4/D6CBA4.png) | 15.63 | 17 | 11.03 | 15 | +2 |
| GARMENT_19 | ![](https://placehold.co/20x20/9B1A21/9B1A21.png) | ![](https://placehold.co/20x20/D62231/D62231.png) | 21.58 | 8 | 12.15 | 14 | −6 |
| GARMENT_51 | ![](https://placehold.co/20x20/6C655A/6C655A.png) | ![](https://placehold.co/20x20/7C8265/7C8265.png) | 15.16 | 18 | 14.46 | 13 | +5 |
| GARMENT_33 | ![](https://placehold.co/20x20/17224E/17224E.png) | ![](https://placehold.co/20x20/2A32A8/2A32A8.png) | 45.92 | 1 | 14.82 | 12 | **−11** |
| GARMENT_50 | ![](https://placehold.co/20x20/82A1A0/82A1A0.png) | ![](https://placehold.co/20x20/AFC4D6/AFC4D6.png) | 18.08 | 14 | 15.07 | 11 | +3 |
| GARMENT_41 | ![](https://placehold.co/20x20/637D7C/637D7C.png) | ![](https://placehold.co/20x20/8FA7AE/8FA7AE.png) | 17.17 | 16 | 15.45 | 10 | +6 |
| GARMENT_5 | ![](https://placehold.co/20x20/7D9681/7D9681.png) | ![](https://placehold.co/20x20/A8CBA4/A8CBA4.png) | 20.94 | 10 | 15.52 | 9 | +1 |
| GARMENT_36 | ![](https://placehold.co/20x20/637983/637983.png) | ![](https://placehold.co/20x20/93A3A3/93A3A3.png) | 17.46 | 15 | 15.69 | 8 | +7 |
| GARMENT_12 | ![](https://placehold.co/20x20/A7A699/A7A699.png) | ![](https://placehold.co/20x20/DCE0B4/DCE0B4.png) | 25.47 | 4 | 17.34 | 7 | −3 |
| GARMENT_17 | ![](https://placehold.co/20x20/9F3829/9F3829.png) | ![](https://placehold.co/20x20/E15A3C/E15A3C.png) | 22.78 | 6 | 17.43 | 6 | 0 |
| GARMENT_21 | ![](https://placehold.co/20x20/71151B/71151B.png) | ![](https://placehold.co/20x20/B94550/B94550.png) | 23.42 | 5 | 18.39 | 5 | 0 |
| GARMENT_18 | ![](https://placehold.co/20x20/A12625/A12625.png) | ![](https://placehold.co/20x20/E8544B/E8544B.png) | 21.60 | 7 | 19.32 | 4 | +3 |
| GARMENT_1 | ![](https://placehold.co/20x20/96446A/96446A.png) | ![](https://placehold.co/20x20/C275AC/C275AC.png) | 21.47 | 9 | 19.34 | 3 | +6 |
| GARMENT_39 | ![](https://placehold.co/20x20/4B707B/4B707B.png) | ![](https://placehold.co/20x20/87B7C6/87B7C6.png) | 26.86 | 3 | 24.12 | 2 | +1 |
| GARMENT_29 | ![](https://placehold.co/20x20/D2305B/D2305B.png) | ![](https://placehold.co/20x20/EE8FC0/EE8FC0.png) | 40.35 | 2 | 24.43 | 1 | +1 |



*Averages: CIE76 = 14.2, CIEDE2000 = 9.9 (1.44× larger). Ranking agreement:
Spearman ρ = 0.93. 8/48 unchanged, mean absolute shift 3.6 places, max 18.*