"""Post-hoc diagnostics preserve frozen strict grades and separate value/format differences."""

import re
from decimal import Decimal, InvalidOperation

INTEGER = re.compile(r"[+-]?[0-9]+\Z")
KEYWORD_PAIRS = {"61692", "62222"}


def diagnose(pair: str, expected: str, execution: dict) -> str:
    if execution.get("status") != "ok" or execution.get("stdout_truncated"):
        return "inconclusive_execution"
    actual = execution.get("stdout", "")
    if actual == expected:
        return "exact_match"
    actual, expected = actual.strip(), expected.strip()
    if actual == expected:
        return "format_difference"
    if pair in KEYWORD_PAIRS:
        allowed = {"hon", "pon", "bon"} if pair == "61692" else {"Yes", "No"}
        if actual in allowed:
            return "functional_value_mismatch"
        return (
            "format_difference"
            if actual.casefold() == expected.casefold()
            else "stdout_contract_violation"
        )
    if pair == "61358":
        parts, correct = actual.split(":"), expected.split(":")
        if len(parts) == 3 and all(INTEGER.fullmatch(value) for value in parts):
            return (
                "format_difference"
                if list(map(int, parts)) == list(map(int, correct))
                else "functional_value_mismatch"
            )
        return "stdout_contract_violation"
    if INTEGER.fullmatch(actual):
        return "format_difference" if int(actual) == int(expected) else "functional_value_mismatch"
    # Equal decimal values may fail the integer format contract without a value error.
    try:
        if Decimal(actual) == Decimal(expected):
            return "numeric_representation_difference"
    except InvalidOperation:
        pass
    return "stdout_contract_violation"
