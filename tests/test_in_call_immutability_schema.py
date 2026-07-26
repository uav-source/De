from __future__ import annotations

import pytest

from fastlio2_adapter.in_call_immutability import (
    CHECKSUM_ALGORITHM,
    InCallImmutabilityError,
    SCHEMA_VERSION,
    expected_status_checksum,
    validate_status,
)


def valid_status() -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "enabled": True,
        "audited_call_count": 3,
        "all_unchanged_count": 3,
        "mutation_detected_count": 0,
        "state_mismatch_count": 0,
        "covariance_mismatch_count": 0,
        "jacobian_mismatch_count": 0,
        "innovation_mismatch_count": 0,
        "geometric_residual_mismatch_count": 0,
        "accepted_index_mismatch_count": 0,
        "correspondence_mismatch_count": 0,
        "map_size_mismatch_count": 0,
        "first_mismatch": None,
        "tap_call_attempt_count": 3,
        "tap_record_emitted_count": 3,
        "nonfinite_checksum_input_count": 0,
        "internal_audit_error_count": 0,
    }
    value["audit_status_checksum"] = expected_status_checksum(value)
    return value


def test_valid_status_passes() -> None:
    assert validate_status(valid_status())["audited_call_count"] == 3


def test_missing_field_fails_closed() -> None:
    value = valid_status()
    del value["accepted_index_mismatch_count"]
    with pytest.raises(InCallImmutabilityError):
        validate_status(value)


def test_bad_checksum_fails_closed() -> None:
    value = valid_status()
    value["audit_status_checksum"] = "FNV1A64:0000000000000000"
    with pytest.raises(InCallImmutabilityError):
        validate_status(value)


def test_negative_count_fails_closed() -> None:
    value = valid_status()
    value["audited_call_count"] = -1
    with pytest.raises(InCallImmutabilityError):
        validate_status(value)


def test_first_mismatch_shape_is_bounded() -> None:
    value = valid_status()
    value["first_mismatch"] = {
        "scan_index": 4,
        "measurement_call_index": 1,
        "fields": ["map_size"],
        "before_after": {
            "map_size": {"before": 100, "after": 101},
        },
    }
    value["audit_status_checksum"] = expected_status_checksum(value)
    assert validate_status(value)["first_mismatch"] is not None
