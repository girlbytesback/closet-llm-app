# 🖍️ Color Extraction Eval — LLM/VLM vs. Measured Truth 🖌️
 
**What this measures:** how accurately the model reads the dominant color
of a garment photo, compared against colors measured by hand.
Distance is scored with the **CIEDE2000 (ΔE)** math formula — a
color-difference calculation where smaller means closer, and roughly:
 
- **ΔE ≤ 2.0 - 5.0** — difference barely noticable to the human eye
- **ΔE ≤ 10** — perceptible, but still in the right color neighborhood
- **ΔE > 10** — clearly a different color

sample size: **48 garments.**
 
---
 
## TLDR !! 💭
 
The model is effective at generating the main color of a garment, but will not **produce exact color,
will often just return one from a similar color family**. 

 Only **9/48 (19%)** land within ΔE ≤ 5, though **32/48 (67%)** land within ΔE ≤ 10.
- The errors are **not random**. The model consistently reports colors that are
  **lighter and more saturated** than reality:
  - lighter in **36/48** garments (mean **+7.3** in L\*)
  - more saturated in **38/48** garments (mean **+5.3** in chroma)
- The bias is **worst on dark, saturated reds and pinks** and best on **dark
  neutrals** (near-blacks are the tightest matches).
- Because the error has a **consistent direction**, the fix is a real engineering
  change — sample pixels directly from the image with PIL instead of asking the
  model to name a hex — **not** just loosening the pass threshold.
| Threshold | Meaning | Pass rate |
|---|---|---|
| ΔE ≤ 2 | imperceptible | 1/48 (2%) |
| ΔE ≤ 5 | barely perceptible | 9/48 (19%) |
| **ΔE ≤ 10** | **perceptible, usable for palette bucketing** | **32/48 (67%)** |
 
Mean ΔE = **9.9**, median ΔE = **8.1**.
 
---
 
## Why the threshold is set at ΔE ≤ 10:
 
This eval reports a pass at **ΔE ≤ 10**, not the stricter ΔE ≤ 5. That is a
deliberate choice tied to what the app actually needs: it sorts garments into
broad palette buckets, not exact swatches. At ΔE ≤ 10 a color is still in the
correct family (a muted teal reads as a muted teal), which is the tolerance the
matching step needs.
 
The looser threshold is **not** a way to hide the error — the lighter/more-saturated
bias below is reported in full regardless of where the pass line sits. Raising the
line changes what counts as "good enough for this product," not what the model did.
 
---
 
## Evaluating Failures:
 
The failures share one direction. The model almost always pushes colors **lighter**
and **more vivid** than the measured truth:
 
- **Lightness (L\*):** model is lighter in **36 of 48** garments, by **+7.3** on average.
- **Chroma (saturation):** model is more saturated in **38 of 48** garments, by **+5.3** on average.
That "same direction most of the time" is the signal that this is a **systematic
bias**, not noise. A few concrete examples:
 
- **GARMENT_29** — a punchy magenta (`#D2305B`) reported as pastel pink (`#EE8FC0`), ΔE 24.4.
- **GARMENT_21** — a deep brick red (`#71151B`) reported as a bright rosy red (`#B94550`), ΔE 18.4.
- The saturated reds (17, 18, 19, 21) all get dragged brighter and oranger.
Where the model behaves: **dark neutrals**. The four tightest matches
(GARMENT_47, 3, 55, 28) are near-blacks and one clean saturated pink — low-lightness
colors leave little room to over-lighten.
 
---
 
## Addressing Biases:
 
The bias points to a specific fix: stop asking the model to *name* a hex code, and
instead **sample the pixels directly** from the garment region with PIL and compute
the dominant color deterministically. That removes the perceptual guesswork that
produces the lightening, and it should be validated by re-running this exact eval
and checking the mean L\* / chroma bias shrinks toward zero.
 
---
 
## RESULTS:
 
Threshold: **ΔE ≤ 10.0 = PASS.**
 
| Garment | Measured (truth) | Model said | ΔE2000 | Status |
|---|---|---|---|---|
| GARMENT_47 | ![](https://placehold.co/20x20/0B0A08/0B0A08.png) `#0B0A08` | ![](https://placehold.co/20x20/101010/101010.png) `#101010` | 1.4 | ✅ |
| GARMENT_28 | ![](https://placehold.co/20x20/D2305B/D2305B.png) `#D2305B` | ![](https://placehold.co/20x20/CE2751/CE2751.png) `#CE2751` | 2.4 | ✅ |
| GARMENT_55 | ![](https://placehold.co/20x20/3D3432/3D3432.png) `#3D3432` | ![](https://placehold.co/20x20/332E2E/332E2E.png) `#332E2E` | 3.2 | ✅ |
| GARMENT_8 | ![](https://placehold.co/20x20/91A193/91A193.png) `#91A193` | ![](https://placehold.co/20x20/94A891/94A891.png) `#94A891` | 4.0 | ✅ |
| GARMENT_46 | ![](https://placehold.co/20x20/E2E3DE/E2E3DE.png) `#E2E3DE` | ![](https://placehold.co/20x20/F5F0E8/F5F0E8.png) `#F5F0E8` | 4.2 | ✅ |
| GARMENT_26 | ![](https://placehold.co/20x20/9D6687/9D6687.png) `#9D6687` | ![](https://placehold.co/20x20/A85C7E/A85C7E.png) `#A85C7E` | 4.5 | ✅ |
| GARMENT_24 | ![](https://placehold.co/20x20/B5AE84/B5AE84.png) `#B5AE84` | ![](https://placehold.co/20x20/C4B183/C4B183.png) `#C4B183` | 4.7 | ✅ |
| GARMENT_3 | ![](https://placehold.co/20x20/1E1E20/1E1E20.png) `#1E1E20` | ![](https://placehold.co/20x20/2A2724/2A2724.png) `#2A2724` | 4.7 | ✅ |
| GARMENT_32 | ![](https://placehold.co/20x20/313A46/313A46.png) `#313A46` | ![](https://placehold.co/20x20/2B3040/2B3040.png) `#2B3040` | 4.9 | ✅ |
| GARMENT_52 | ![](https://placehold.co/20x20/020200/020200.png) `#020200` | ![](https://placehold.co/20x20/15161A/15161A.png) `#15161A` | 5.5 | ✅ |
| GARMENT_37 | ![](https://placehold.co/20x20/3A3D3F/3A3D3F.png) `#3A3D3F` | ![](https://placehold.co/20x20/2B3038/2B3038.png) `#2B3038` | 5.6 | ✅ |
| GARMENT_14 | ![](https://placehold.co/20x20/D2DFA3/D2DFA3.png) `#D2DFA3` | ![](https://placehold.co/20x20/B9D183/B9D183.png) `#B9D183` | 5.8 | ✅ |
| GARMENT_9 | ![](https://placehold.co/20x20/544D2C/544D2C.png) `#544D2C` | ![](https://placehold.co/20x20/5C5A2C/5C5A2C.png) `#5C5A2C` | 5.8 | ✅ |
| GARMENT_20 | ![](https://placehold.co/20x20/751722/751722.png) `#751722` | ![](https://placehold.co/20x20/8E1D33/8E1D33.png) `#8E1D33` | 5.8 | ✅ |
| GARMENT_38 | ![](https://placehold.co/20x20/3D4048/3D4048.png) `#3D4048` | ![](https://placehold.co/20x20/2A2E3A/2A2E3A.png) `#2A2E3A` | 6.3 | ✅ |
| GARMENT_40 | ![](https://placehold.co/20x20/7D869B/7D869B.png) `#7D869B` | ![](https://placehold.co/20x20/8296B4/8296B4.png) `#8296B4` | 6.6 | ✅ |
| GARMENT_4 | ![](https://placehold.co/20x20/573F3B/573F3B.png) `#573F3B` | ![](https://placehold.co/20x20/6B4238/6B4238.png) `#6B4238` | 6.6 | ✅ |
| GARMENT_45 | ![](https://placehold.co/20x20/D3D2CB/D3D2CB.png) `#D3D2CB` | ![](https://placehold.co/20x20/F2F1EF/F2F1EF.png) `#F2F1EF` | 7.4 | ✅ |
| GARMENT_31 | ![](https://placehold.co/20x20/30303C/30303C.png) `#30303C` | ![](https://placehold.co/20x20/1E1E22/1E1E22.png) `#1E1E22` | 7.4 | ✅ |
| GARMENT_13 | ![](https://placehold.co/20x20/BBB97F/BBB97F.png) `#BBB97F` | ![](https://placehold.co/20x20/B7C464/B7C464.png) `#B7C464` | 7.5 | ✅ |
| GARMENT_53 | ![](https://placehold.co/20x20/606C6C/606C6C.png) `#606C6C` | ![](https://placehold.co/20x20/455B5D/455B5D.png) `#455B5D` | 7.8 | ✅ |
| GARMENT_15 | ![](https://placehold.co/20x20/273F3D/273F3D.png) `#273F3D` | ![](https://placehold.co/20x20/1F4A3D/1F4A3D.png) `#1F4A3D` | 8.0 | ✅ |
| GARMENT_2 | ![](https://placehold.co/20x20/1B3671/1B3671.png) `#1B3671` | ![](https://placehold.co/20x20/334F84/334F84.png) `#334F84` | 8.0 | ✅ |
| GARMENT_49 | ![](https://placehold.co/20x20/B8DCDE/B8DCDE.png) `#B8DCDE` | ![](https://placehold.co/20x20/B9D6E8/B9D6E8.png) `#B9D6E8` | 8.1 | ✅ |
| GARMENT_34 | ![](https://placehold.co/20x20/C4C6C5/C4C6C5.png) `#C4C6C5` | ![](https://placehold.co/20x20/B4C6D4/B4C6D4.png) `#B4C6D4` | 8.2 | ✅ |
| GARMENT_42 | ![](https://placehold.co/20x20/999174/999174.png) `#999174` | ![](https://placehold.co/20x20/B6AC8C/B6AC8C.png) `#B6AC8C` | 8.5 | ✅ |
| GARMENT_48 | ![](https://placehold.co/20x20/CBC7BF/CBC7BF.png) `#CBC7BF` | ![](https://placehold.co/20x20/F2EADA/F2EADA.png) `#F2EADA` | 8.8 | ✅ |
| GARMENT_23 | ![](https://placehold.co/20x20/D1C6B0/D1C6B0.png) `#D1C6B0` | ![](https://placehold.co/20x20/F2E9C8/F2E9C8.png) `#F2E9C8` | 8.8 | ✅ |
| GARMENT_27 | ![](https://placehold.co/20x20/BFA5BA/BFA5BA.png) `#BFA5BA` | ![](https://placehold.co/20x20/E5C3D1/E5C3D1.png) `#E5C3D1` | 9.0 | ✅ |
| GARMENT_10 | ![](https://placehold.co/20x20/979C78/979C78.png) `#979C78` | ![](https://placehold.co/20x20/7C8A52/7C8A52.png) `#7C8A52` | 9.1 | ✅ |
| GARMENT_25 | ![](https://placehold.co/20x20/4C1421/4C1421.png) `#4C1421` | ![](https://placehold.co/20x20/7B1F35/7B1F35.png) `#7B1F35` | 9.9 | ✅ |
| GARMENT_54 | ![](https://placehold.co/20x20/D7BDBA/D7BDBA.png) `#D7BDBA` | ![](https://placehold.co/20x20/F7E4DA/F7E4DA.png) `#F7E4DA` | 9.97 | ✅ |
| GARMENT_16 | ![](https://placehold.co/20x20/9E3134/9E3134.png) `#9E3134` | ![](https://placehold.co/20x20/C0402C/C0402C.png) `#C0402C` | 10.5 | ❌ |
| GARMENT_22 | ![](https://placehold.co/20x20/BDB1A3/BDB1A3.png) `#BDB1A3` | ![](https://placehold.co/20x20/D6CBA4/D6CBA4.png) `#D6CBA4` | 11.0 | ❌ |
| GARMENT_19 | ![](https://placehold.co/20x20/9B1A21/9B1A21.png) `#9B1A21` | ![](https://placehold.co/20x20/D62231/D62231.png) `#D62231` | 12.2 | ❌ |
| GARMENT_51 | ![](https://placehold.co/20x20/6C655A/6C655A.png) `#6C655A` | ![](https://placehold.co/20x20/7C8265/7C8265.png) `#7C8265` | 14.5 | ❌ |
| GARMENT_33 | ![](https://placehold.co/20x20/17224E/17224E.png) `#17224E` | ![](https://placehold.co/20x20/2A32A8/2A32A8.png) `#2A32A8` | 14.8 | ❌ |
| GARMENT_50 | ![](https://placehold.co/20x20/82A1A0/82A1A0.png) `#82A1A0` | ![](https://placehold.co/20x20/AFC4D6/AFC4D6.png) `#AFC4D6` | 15.1 | ❌ |
| GARMENT_5 | ![](https://placehold.co/20x20/7D9681/7D9681.png) `#7D9681` | ![](https://placehold.co/20x20/A8CBA4/A8CBA4.png) `#A8CBA4` | 15.5 | ❌ |
| GARMENT_41 | ![](https://placehold.co/20x20/637D7C/637D7C.png) `#637D7C` | ![](https://placehold.co/20x20/8FA7AE/8FA7AE.png) `#8FA7AE` | 15.5 | ❌ |
| GARMENT_36 | ![](https://placehold.co/20x20/637983/637983.png) `#637983` | ![](https://placehold.co/20x20/93A3A3/93A3A3.png) `#93A3A3` | 15.7 | ❌ |
| GARMENT_12 | ![](https://placehold.co/20x20/A7A699/A7A699.png) `#A7A699` | ![](https://placehold.co/20x20/DCE0B4/DCE0B4.png) `#DCE0B4` | 17.3 | ❌ |
| GARMENT_17 | ![](https://placehold.co/20x20/9F3829/9F3829.png) `#9F3829` | ![](https://placehold.co/20x20/E15A3C/E15A3C.png) `#E15A3C` | 17.4 | ❌ |
| GARMENT_21 | ![](https://placehold.co/20x20/71151B/71151B.png) `#71151B` | ![](https://placehold.co/20x20/B94550/B94550.png) `#B94550` | 18.4 | ❌ |
| GARMENT_18 | ![](https://placehold.co/20x20/A12625/A12625.png) `#A12625` | ![](https://placehold.co/20x20/E8544B/E8544B.png) `#E8544B` | 19.3 | ❌ |
| GARMENT_1 | ![](https://placehold.co/20x20/96446A/96446A.png) `#96446A` | ![](https://placehold.co/20x20/C275AC/C275AC.png) `#C275AC` | 19.3 | ❌ |
| GARMENT_39 | ![](https://placehold.co/20x20/4B707B/4B707B.png) `#4B707B` | ![](https://placehold.co/20x20/87B7C6/87B7C6.png) `#87B7C6` | 24.1 | ❌ |
| GARMENT_29 | ![](https://placehold.co/20x20/D2305B/D2305B.png) `#D2305B` | ![](https://placehold.co/20x20/EE8FC0/EE8FC0.png) `#EE8FC0` | 24.4 | ❌ |
 
*Note: GARMENT_54's raw ΔE is 9.9687 — it rounds to 10.0 in display but is
genuinely below the threshold, so it passes. Counting the rounded column would
have mislabeled it. Pass count is 32/48.*
