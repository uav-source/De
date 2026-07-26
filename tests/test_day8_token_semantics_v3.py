import csv
import json

import pytest

from fastlio2_adapter.day8_token_semantics_v3 import (
    CAPTURED_NONEMPTY,
    CAPTURE_FAILED,
    EVIDENCE_GAP_NOT_CAPTURED,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    OVERFLOWED,
    audit_output_paths,
    compare_token_sequences,
    json_csv_null_roundtrip_pass,
    validate_token_comparison_record,
)


def token(depth=0):
    return {"token_index": 0, "depth": depth}


def test_captured_sequences_compare_as_booleans():
    equal = compare_token_sequences(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, [token()], [token()]
    )
    different = compare_token_sequences(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, [token()], [token(1)]
    )
    assert equal["token_sequence_equal"] is True
    assert different["token_sequence_equal"] is False


def test_not_captured_is_null_and_evidence_gap():
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        CAPTURED_NONEMPTY,
        (),
        [token()],
    )
    assert value["token_comparison_status"] == "NOT_APPLICABLE"
    assert value["token_sequence_equal"] is None
    assert value["classification"] == "EVIDENCE_GAP"
    assert value["root_cause_classification"] == EVIDENCE_GAP_NOT_CAPTURED


@pytest.mark.parametrize("status", [CAPTURE_FAILED, OVERFLOWED])
def test_fatal_capture_status_fails_gate(status):
    value = compare_token_sequences(status, CAPTURED_NONEMPTY, (), [token()])
    assert value["capture_gate_pass"] is False


def test_validator_rejects_not_captured_equal_true():
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        CAPTURED_NONEMPTY,
        (),
        [token()],
    )
    value["token_sequence_equal"] = True
    with pytest.raises(ValueError):
        validate_token_comparison_record(value)


def test_recursive_json_csv_null_roundtrip(tmp_path):
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        CAPTURED_NONEMPTY,
        (),
        [token()],
    )
    json_path = tmp_path / "value.json"
    json_path.write_text(json.dumps({"nested": [value]}), encoding="utf-8")
    csv_path = tmp_path / "value.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(value))
        writer.writeheader()
        writer.writerow(value)
    audit = audit_output_paths([json_path, csv_path])
    assert audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"]
    assert json_csv_null_roundtrip_pass()
