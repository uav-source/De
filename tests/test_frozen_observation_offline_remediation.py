import json
from pathlib import Path

from fastlio2_adapter.frozen_observation import (
    validate_core_observation_integrity,
)
from fastlio2_adapter.frozen_observation_archive import (
    replace_json_personal_paths,
    scan_personal_absolute_paths,
)


def invariants():
    return {
        "core_binary_sha256": "a" * 64,
        "binary_size_bytes": 100,
        "observation_record_count": 3,
        "binary_trailer_count": 3,
        "record_index_sha256": "b" * 64,
        "record_index_row_count": 3,
        "scan_index_sequence_sha256": "c" * 64,
        "binary_offset_sequence_sha256": "d" * 64,
        "runtime_scan_count": 5,
        "skipped_scan_count": 2,
        "schema_rejected_record_count": 0,
        "nonfinite_record_count": 0,
        "forbidden_field_count": 0,
        "gt_topic_consumed_count": 0,
        "tap_drop_count": 0,
        "writer_error_count": 0,
        "binary_checksum_failure_count": 0,
        "truncated_record_count": 0,
    }


def test_core_binary_sha_change_fails_integrity():
    before = invariants()
    after = invariants()
    after["core_binary_sha256"] = "e" * 64
    result = validate_core_observation_integrity(before, after)
    assert result["mismatch_count"] == 1
    assert result["core_observation_data_integrity_pass"] is False


def test_record_count_change_fails_integrity():
    before = invariants()
    after = invariants()
    after["observation_record_count"] = 2
    assert validate_core_observation_integrity(before, after)[
        "core_observation_data_integrity_pass"
    ] is False


def test_json_path_is_replaced_with_relative_alias(tmp_path: Path):
    root = tmp_path / "frozen"
    root.mkdir()
    leaked = (
        "/"
        + "home"
        + "/lj/runtime/observation_records_v3.bin"
    )
    path = root / "summary.json"
    path.write_text(json.dumps({"path": leaked}), encoding="utf-8")
    records = replace_json_personal_paths(root)
    assert len(records) == 1
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value == {
        "path_alias": "binary/observation_records_v3.bin"
    }
    assert scan_personal_absolute_paths(root)[
        "content_absolute_path_scan_pass"
    ] is True
    assert leaked not in json.dumps(records)
