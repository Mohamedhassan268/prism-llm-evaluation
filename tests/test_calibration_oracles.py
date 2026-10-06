import pytest
from hypothesis import given
from hypothesis import strategies as st

from prismqa.calibration_oracles import (
    answer,
    digits,
    flipping_signs,
    interest,
    requirements,
    vacation,
)


def test_official_examples_and_exhaustive_searches():
    assert flipping_signs([-10, 5, -4]) == 19
    assert flipping_signs([10, -4, -8, -11, 3]) == 30
    assert flipping_signs([-1, 0, 2]) == 3
    assert vacation([(1, 2), (1, 3), (1, 4), (2, 1), (2, 3)], 3) == 10
    assert vacation([(2, 1)], 1) == 0
    assert requirements(3, 4, [(1, 3, 3, 100), (1, 2, 2, 10), (2, 3, 2, 10)]) == 110
    assert interest(101) == 1
    assert interest(10**18) == 3760
    assert interest(1333333333) == 1706
    assert answer("61358", "86400\n") == "24:0:0\n"
    assert answer("62549", "4\naaaa\na\naaa\naa\n") == "4\n"


@given(st.integers(1, 10**9), st.integers(2, 10))
def test_digit_count_agrees_with_power_interval(n, base):
    count = digits(n, base)
    assert base ** (count - 1) <= n < base**count


@pytest.mark.parametrize(
    "pair,value",
    [
        ("62222", "9\n"),
        ("59448", "0\n"),
        ("61692", "1000\n"),
        ("60265", "100\n"),
        ("58902", "0 2\n"),
        ("62549", "1\nUPPER\n"),
    ],
)
def test_invalid_inputs_are_rejected(pair, value):
    with pytest.raises(ValueError):
        answer(pair, value)


def test_duplicate_requirement_is_invalid():
    with pytest.raises(ValueError, match="Duplicate"):
        requirements(2, 2, [(1, 2, 1, 1), (1, 2, 1, 5)])
