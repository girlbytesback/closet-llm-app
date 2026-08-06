"""
Nothing here talks to the API. extract.py turns photos into hex codes once and
caches them; from that point on, matching is arithmetic that gives the same
answer every time it runs.
"""

from __future__ import annotations
from math import atan2, cos, degrees, exp, hypot, radians, sin, sqrt
from typing import Dict, List, Sequence, Tuple
import re

regex_hex = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# D65 white point — the color of the light everything is measured against.
# Dividing by it is what makes a white shirt read as white both indoors and out.
_WHITE = (0.95047, 1.00000, 1.08883)


def validate_hex_value(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"not a hex color: {value!r}")

    hex_value = regex_hex.match(value.strip())
    if not hex_value:
        raise ValueError(f"not a hex color: {value!r}")

    digits = hex_value.group(1)

    # fill in remainder of hex value to have correct amount of digits
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.upper()


def hex_to_rgb(value: str) -> Tuple[float, float, float]:
    """Stage 1-2. '#C071A8' -> (0.7529, 0.4431, 0.6588).

    Base-16 arithmetic: C0 = 12*16 + 0 = 192, then divide by 255 because
    everything downstream expects fractions rather than 0-255.

    calculations + numbers derived from online
    """
    digits = validate_hex_value(value).lstrip("#")
    return tuple(int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _linearize(channel: float) -> float:
    #undos bend in RGB curvature to make more visible to human eye
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_xyz(rgb: Sequence[float]) -> Tuple[float, float, float]:
    """computer screen -> eye.

    where r, g. b = computer monitor light emitting
    and x, y, z = coordinates that translate to human eye
    """

    r, g, b = (_linearize(c) for c in rgb)
    return (
        0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
        0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
        0.0193339 * r + 0.1191920 * g + 0.9503041 * b,
    )


def xyz_to_lab(xyz: Sequence[float]) -> Tuple[float, float, float]:
    """"
    cube root models how perception compresses — doubling the
    light doesn't double the brightness you experience. The subtractions model
    how your brain actually receives color: not as red/green/blue, but as three
    comparisons. That's why "reddish green" isn't imaginable — one channel
    can't be at both ends.

        l = lightness, 0 to 100
        a = green (negative) to red (positive)
        b = blue (negative) to yellow (positive)
    """
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = (f(c / w) for c, w in zip(xyz, _WHITE))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def hex_to_lab(value: str) -> Tuple[float, float, float]:
    #executes entire flow
    return xyz_to_lab(rgb_to_xyz(hex_to_rgb(value)))


def lab_to_lch(lab: Sequence[float]) -> Tuple[float, float, float]:
    """
    your garment is one color where three hex codes turned out to be one pink 
    at three lightnesses: identical hue, identical chroma, only L moving. 
    shadow and highlight
    """
    lightness, a, b = lab
    return (lightness, hypot(a, b), degrees(atan2(b, a)) % 360)


def delta_e_76(lab1: Sequence[float], lab2: Sequence[float]) -> float:
    """pythagorean theorem for distancce formula 
    sqrt((L1-L2)^2 + (a1-a2)^2 + (b1-b2)^2)
    """
    return sqrt(sum((x - y) ** 2 for x, y in zip(lab1, lab2)))


def delta_e_2000(lab1: Sequence[float], lab2: Sequence[float]) -> float:
    """CIEDE2000. Same idea as above, plus correction terms.

    Lab still isn't perfectly even, so this scales the lightness, chroma and
    hue differences depending on where in the space you are. Every one of those
    corrections was fitted to survey data — people were shown color pairs and
    asked which looked more different. That's why the formula is ugly: it's
    curve-fitting to human judgement, not elegant theory.

    Validated against 23 published reference pairs.

    Reading the number:
        under 1   indistinguishable
        1 to 2    visible on close inspection
        2 to 10   clearly different, still related
        over 20   different colors
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1, c2 = hypot(a1, b1), hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7))) if c_bar else 0.5

    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = hypot(a1p, b1), hypot(a2p, b2)

    h1p = degrees(atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = degrees(atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    d_lp = l2 - l1
    d_cp = c2p - c1p

    if c1p * c2p == 0:
        d_hp = 0.0
    elif abs(h2p - h1p) <= 180:
        d_hp = h2p - h1p
    elif h2p - h1p > 180:
        d_hp = h2p - h1p - 360
    else:
        d_hp = h2p - h1p + 360
    d_hp_cap = 2 * sqrt(c1p * c2p) * sin(radians(d_hp / 2))

    l_bar = (l1 + l2) / 2
    c_barp = (c1p + c2p) / 2

    if c1p * c2p == 0:
        h_barp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_barp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_barp = (h1p + h2p + 360) / 2
    else:
        h_barp = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * cos(radians(h_barp - 30))
        + 0.24 * cos(radians(2 * h_barp))
        + 0.32 * cos(radians(3 * h_barp + 6))
        - 0.20 * cos(radians(4 * h_barp - 63))
    )

    d_theta = 30 * exp(-(((h_barp - 275) / 25) ** 2))
    r_c = 2 * sqrt(c_barp ** 7 / (c_barp ** 7 + 25 ** 7)) if c_barp else 0.0
    s_l = 1 + (0.015 * (l_bar - 50) ** 2) / sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_barp
    s_h = 1 + 0.015 * c_barp * t
    r_t = -sin(radians(2 * d_theta)) * r_c

    return sqrt(
        (d_lp / s_l) ** 2
        + (d_cp / s_c) ** 2
        + (d_hp_cap / s_h) ** 2
        + r_t * (d_cp / s_c) * (d_hp_cap / s_h)
    )

def distance(hex1: str, hex2: str) -> float:
    """Two hex codes in, one number out. Lower means more alike."""
    return delta_e_2000(hex_to_lab(hex1), hex_to_lab(hex2))

default_cutoff = 25.0

def score_garment(palette_color: str, garment_colors: Sequence[str]) -> float:
    """How close a garment gets to one palette color.

    Today every garment has a single color, so this is just one distance. The
    min() is there for later: when a garment has several colors, "does any part
    of this pick up the palette color" is the right question, and this line
    already answers it with no change.
    """
    return min(distance(palette_color, g) for g in garment_colors)

def matches_for_color(
    palette_color: str,
    closet: Dict[str, Sequence[str]],
    cutoff: float = default_cutoff,
) -> List[Tuple[str, float]]:
    """Every garment close enough to one palette color, nearest first."""
    hits = [
        (name, score_garment(palette_color, colors))
        for name, colors in closet.items()
    ]
    return sorted((h for h in hits if h[1] <= cutoff), key=lambda pair: pair[1])

def matches_by_color(
    palette_colors: Sequence[str],
    closet: Dict[str, Sequence[str]],
    cutoff: float = default_cutoff,
) -> Dict[str, List[Tuple[str, float]]]:
    """One list of garments per palette color — the shape the UI wants.

    {"#B5C29A": [("green_top.jpeg", 12.4)],
     "#E4A8C0": [("pink_shirt.jpeg", 8.1), ("rose_dress.jpeg", 19.0)]}
    """
    return {c: matches_for_color(c, closet, cutoff) for c in palette_colors}

neutral_chroma = 12.0  # below this a color reads as a neutral

def is_neutral(hex_value: str) -> bool:
    """Blacks, whites, greys, most beiges.

    Their hue angle is numerical noise, so hue rules produce nonsense on them.
    Worth knowing about because a palette containing a near-black will match
    every dark garment you own — see either_or_both.html, "The catch".
    """
    return lab_to_lch(hex_to_lab(hex_value))[1] < neutral_chroma


def hue_gap(hex1: str, hex2: str) -> float:
    """Smallest angle between two hues, 0-180.

    The wheel wraps: 350 degrees and 10 degrees are 20 apart, not 340.
    """
    h1 = lab_to_lch(hex_to_lab(hex1))[2]
    h2 = lab_to_lch(hex_to_lab(hex2))[2]
    gap = abs(h1 - h2) % 360
    return 360 - gap if gap > 180 else gap
