from __future__ import annotations

import pytest

from fastlio2_adapter.experiment_a_stage_hash import (
    HASH_ALGORITHM,
    MAP_DIGEST_VERSION,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    SNAPSHOT_METHOD,
    SNAPSHOT_SCHEMA_VERSION,
    STATUS_SCHEMA_VERSION,
    ExperimentAStageHashError,
    validate_record,
    validate_status,
)


def record(scan: int) -> dict[str, object]:
    value: dict[str, object] = {field: 1 for field in REQUIRED_FIELDS}
    for field in value:
        if "nonfinite_count" in field:
            value[field] = 0
    value.update(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": "r1",
            "scan_index": scan,
            "timestamp_begin": float(scan),
            "timestamp_end": float(scan) + 0.1,
            "window_start": 135,
            "window_end": 160,
            "window_enabled": True,
            "map_insertion_executed": True,
            "diagnostic_read_only_check_pass": True,
            "diagnostic_internal_error": False,
        }
    )
    for prefix, stage in (
        ("map_before", "map_snapshot_before_measurement"),
        ("map_after", "map_snapshot_after_all_map_mutations"),
    ):
        value.update(
            {
                f"{prefix}_snapshot_schema_version":
                    SNAPSHOT_SCHEMA_VERSION,
                f"{prefix}_snapshot_stage": stage,
                f"{prefix}_snapshot_status":
                    "COHERENT_SYNCHRONIZED_COPY",
                f"{prefix}_snapshot_method": SNAPSHOT_METHOD,
                f"{prefix}_snapshot_coherence_pass": True,
                f"{prefix}_snapshot_error": None,
                f"{prefix}_snapshot_attempt_count": 1,
                f"{prefix}_validnum_before": 1,
                f"{prefix}_validnum_after": 1,
                f"{prefix}_snapshot_point_count": 1,
                f"{prefix}_snapshot_nonfinite_point_count": 0,
                f"{prefix}_rebuild_generation_before": 1,
                f"{prefix}_rebuild_generation_after": 1,
                f"{prefix}_mutation_counter_before": 1,
                f"{prefix}_mutation_counter_after": 1,
            }
        )
    value["map_before_content_checksum"] = value[
        "map_content_before_measurement"
    ]
    value["map_before_traversal_checksum"] = value[
        "map_traversal_before_measurement"
    ]
    value["map_after_content_checksum"] = value[
        "map_content_after_insertion"
    ]
    value["map_after_traversal_checksum"] = value[
        "map_traversal_after_insertion"
    ]
    return value


def status() -> dict[str, object]:
    records = [record(scan) for scan in range(135, 161)]
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "enabled": True,
        "hash_algorithm": HASH_ALGORITHM,
        "map_digest_version": MAP_DIGEST_VERSION,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_method": SNAPSHOT_METHOD,
        "diagnostic_mutation_count": 0,
        "internal_error_count": 0,
        "records": records,
    }


def test_stage_record_schema_accepts_compact_hashes() -> None:
    assert validate_record(record(135))["scan_index"] == 135
    assert validate_status(status())["stage_hash_schema_pass"] is True


def test_stage_record_schema_rejects_full_payload_field() -> None:
    value = record(135)
    value["map_points"] = [[1.0, 2.0, 3.0]]
    with pytest.raises(ExperimentAStageHashError, match="forbidden"):
        validate_record(value)


def test_status_discloses_checksum_collision_limitation() -> None:
    validated = validate_status(status())
    assert "may collide" in validated["checksum_collision_limitation"]
