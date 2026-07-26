import json

import pytest

from fastlio2_adapter.day8_overflow_summary import (
    OVERFLOW_FIELDS,
    SCHEMA_VERSION,
    OverflowSummaryValidationError,
    load_overflow_summary,
    parse_overflow_summary,
)


def _valid(**changes):
    value = {
        "schema_version": SCHEMA_VERSION,
        "query_summary_overflow": 0,
        "traversal_token_overflow": 0,
        "formal_result_member_overflow": 0,
        "point_voxel_pair_overflow": 0,
        "schema_error_count": 0,
    }
    value.update(changes)
    return value


def test_valid_zero_summary():
    result = parse_overflow_summary(_valid())
    assert result["overflow_count"] == 0
    assert result["overflow_pass"] is True
    assert result["schema_pass"] is True


def test_valid_nonzero_overflow_is_aggregated_from_four_fields_only():
    result = parse_overflow_summary(_valid(
        query_summary_overflow=1,
        traversal_token_overflow=2,
        formal_result_member_overflow=3,
        point_voxel_pair_overflow=4,
    ))
    assert result["overflow_count"] == 10
    assert result["overflow_pass"] is False


def test_schema_version_is_never_converted_to_integer():
    result = parse_overflow_summary(_valid())
    assert result["schema_version"] == SCHEMA_VERSION


@pytest.mark.parametrize("value", ["wrong", 1, True])
def test_schema_version_mismatch_fails(value):
    with pytest.raises(OverflowSummaryValidationError) as caught:
        parse_overflow_summary(_valid(schema_version=value))
    assert caught.value.code == "SCHEMA_VERSION_MISMATCH"


def test_missing_schema_version_fails():
    value = _valid()
    del value["schema_version"]
    with pytest.raises(OverflowSummaryValidationError) as caught:
        parse_overflow_summary(value)
    assert caught.value.code == "MISSING_REQUIRED_FIELD"


@pytest.mark.parametrize("field", OVERFLOW_FIELDS)
def test_missing_each_overflow_field_fails(field):
    value = _valid()
    del value[field]
    with pytest.raises(OverflowSummaryValidationError) as caught:
        parse_overflow_summary(value)
    assert caught.value.field == field


def test_missing_schema_error_count_fails():
    value = _valid()
    del value["schema_error_count"]
    with pytest.raises(OverflowSummaryValidationError) as caught:
        parse_overflow_summary(value)
    assert caught.value.field == "schema_error_count"


@pytest.mark.parametrize("bad", ["0", True, -1])
def test_string_bool_and_negative_counts_fail(bad):
    with pytest.raises(OverflowSummaryValidationError):
        parse_overflow_summary(_valid(query_summary_overflow=bad))


def test_unknown_string_and_integer_metadata_do_not_enter_sum():
    result = parse_overflow_summary(_valid(
        metadata_text="diagnostic",
        metadata_integer=999,
    ))
    assert result["overflow_count"] == 0
    assert result["unknown_metadata_field_count"] == 2


def test_original_run1_summary_parses(tmp_path):
    path = tmp_path / "day8_query_overflow_summary.json"
    path.write_text(json.dumps(_valid()) + "\n", encoding="utf-8")
    assert load_overflow_summary(path)["overflow_count"] == 0


def test_legacy_all_values_conversion_reproduces_failure():
    value = _valid()
    with pytest.raises(ValueError, match="invalid literal"):
        sum(int(item) for item in value.values())
