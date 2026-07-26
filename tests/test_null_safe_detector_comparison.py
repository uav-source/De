import math

import pytest

from fastlio2_adapter.contract_aware_direct_comparison import compare_null_safe


def test_null_vs_null_is_equal_without_error():
    result = compare_null_safe(None, None)
    assert result == {
        "equal": True,
        "max_abs_error": 0.0,
        "mismatch_type": "NONE",
        "mismatch_types": [],
    }


@pytest.mark.parametrize("left,right", [(None, 1.0), (1.0, None)])
def test_null_numeric_is_structured_mismatch(left, right):
    result = compare_null_safe(left, right)
    assert result["equal"] is False
    assert result["mismatch_type"] == "NULL_VALUE_DOMAIN_MISMATCH"


def test_booleans_are_compared_exactly_not_as_numbers():
    assert compare_null_safe(True, True)["equal"] is True
    assert compare_null_safe(True, False)["mismatch_type"] == (
        "BOOLEAN_VALUE_MISMATCH"
    )
    assert compare_null_safe(True, 1)["mismatch_type"] == "VALUE_TYPE_MISMATCH"


def test_numeric_tolerance_boundary():
    assert compare_null_safe(1.0, 1.0 + 5.0e-13)["equal"] is True
    result = compare_null_safe(1.0, 1.0 + 2.0e-12)
    assert result["equal"] is False
    assert result["mismatch_type"] == "NUMERIC_TOLERANCE_EXCEEDED"


def test_list_uses_recursive_null_and_numeric_rules():
    assert compare_null_safe([1.0, None], [1.0, None])["equal"] is True
    result = compare_null_safe([1.0, None], [1.0, 2.0])
    assert result["mismatch_type"] == "NULL_VALUE_DOMAIN_MISMATCH"


def test_list_length_mismatch_is_structured():
    result = compare_null_safe([1.0], [1.0, 2.0])
    assert result["equal"] is False
    assert result["mismatch_type"] == "LIST_LENGTH_MISMATCH"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_numeric_is_structured_failure(value):
    result = compare_null_safe(value, value)
    assert result["equal"] is False
    assert result["mismatch_type"] == "NONFINITE_NUMERIC_VALUE"


def test_unsupported_types_do_not_raise():
    result = compare_null_safe({"value": 1}, {"value": 1})
    assert result["equal"] is False
    assert result["mismatch_type"] == "UNSUPPORTED_VALUE_TYPE"
