from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.experiment_a_stage_classifier import compare_pair
from fastlio2_adapter.experiment_a_stage_hash import (
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    SNAPSHOT_METHOD,
    SNAPSHOT_SCHEMA_VERSION,
)


def _record(scan: int) -> dict[str, object]:
    value: dict[str, object] = {field: 1000 + scan for field in REQUIRED_FIELDS}
    for field in value:
        if "nonfinite_count" in field:
            value[field] = 0
    value.update(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": "run",
            "scan_index": scan,
            "timestamp_begin": scan + 0.01,
            "timestamp_end": scan + 0.02,
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
    value["map_count_before_measurement"] = 1
    value["map_count_after_insertion"] = 1
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


def _pair() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    first = [_record(scan) for scan in range(135, 161)]
    second = deepcopy(first)
    for row in second:
        row["run_id"] = "run_2"
    return first, second


def test_raw_lidar_difference_classifies_input() -> None:
    first, second = _pair()
    second[4]["raw_lidar_payload_checksum"] = 999
    result = compare_pair(first, second)
    assert result["stage_classification"] == "INPUT_STAGE_DIVERGED"
    assert result["first_divergence_scan"] == 139


def test_imu_bundle_difference_classifies_input() -> None:
    first, second = _pair()
    second[0]["imu_bundle_checksum"] = 999
    assert compare_pair(first, second)["stage_classification"] == (
        "INPUT_STAGE_DIVERGED"
    )
