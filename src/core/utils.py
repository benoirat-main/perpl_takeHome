"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import math

def test():
    return True

def round_10pct(x: float) -> float:
    if x == 0:
        return 0
    magnitude = 10 ** math.floor(math.log10(abs(x)))
    rounded = round(x / magnitude, 1) * magnitude
    return rounded