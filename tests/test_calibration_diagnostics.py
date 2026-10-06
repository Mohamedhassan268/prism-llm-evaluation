import pytest

from prismqa.calibration_diagnostics import diagnose


@pytest.mark.parametrize(
    "pair,expected,actual,category",
    [
        ("59448", "4\n", "9\n", "functional_value_mismatch"),
        ("59448", "4\n", "4.0\n", "numeric_representation_difference"),
        ("59448", "4\n", " 004 ", "format_difference"),
        ("61358", "1:2:3\n", "01:02:03\n", "format_difference"),
        ("61358", "1:2:3\n", "1:3:2\n", "functional_value_mismatch"),
        ("62222", "Yes\n", "No\n", "functional_value_mismatch"),
        ("62222", "Yes\n", "YES\n", "format_difference"),
        ("59448", "4\n", "Answer: 4\n", "stdout_contract_violation"),
    ],
)
def test_diagnostics_distinguish_math_from_rendering(pair, expected, actual, category):
    assert diagnose(pair, expected, {"status": "ok", "stdout": actual}) == category


def test_truncated_execution_cannot_prove_value_mismatch():
    assert (
        diagnose("59448", "4\n", {"status": "ok", "stdout": "9", "stdout_truncated": True})
        == "inconclusive_execution"
    )
