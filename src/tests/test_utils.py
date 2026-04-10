"""
Author: Benjamin Noirat 
Date: 2026-04-02
"""

import pytest
from src.core.utils import round_10pct


@pytest.mark.parametrize("x,expected", [
    (3.16, 3.2),
    (0.0316, 0.032),
    (1234, 1230),
])

def test_round_relative(x, expected):
    assert round_10pct(x) == pytest.approx(expected)


def test_relative_error_bound():
    for x in [0.0316, 3.16, 1234]:
        y = round_10pct(x)
        assert abs(y - x) / abs(x) <= 0.1