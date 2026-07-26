from __future__ import annotations

from copy import deepcopy

import pytest

from fastlio2_adapter.experiment_a_stage_classifier import compare_pair
from fastlio2_adapter.experiment_a_stage_hash import (
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    SNAPSHOT_METHOD,
    SNAPSHOT_SCHEMA_VERSION,
)


def _rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    first: list[dict[str, object]] = []
    for scan in range(135, 161):
        row: dict[str, object] = {
            field: 100_000 + scan for field in REQUIRED_FIELDS
        }
        for field in row:
            if "nonfinite_count" in field:
                row[field] = 0
        row.update(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": "a",
                "scan_index": scan,
                "timestamp_begin": scan + 0.1,
                "timestamp_end": scan + 0.2,
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
            row.update(
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
        row["map_count_before_measurement"] = 1
        row["map_count_after_insertion"] = 1
        row["map_before_content_checksum"] = row[
            "map_content_before_measurement"
        ]
        row["map_before_traversal_checksum"] = row[
            "map_traversal_before_measurement"
        ]
        row["map_after_content_checksum"] = row[
            "map_content_after_insertion"
        ]
        row["map_after_traversal_checksum"] = row[
            "map_traversal_after_insertion"
        ]
        first.append(row)
    second = deepcopy(first)
    for row in second:
        row["run_id"] = "b"
    return first, second


@pytest.mark.parametrize(
    ("field", "expected"),
    (
        (
            "undistorted_cloud_checksum",
            "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
        ),
        ("map_content_before_measurement", "MAP_STATE_ALREADY_DIVERGED"),
        (
            "map_traversal_before_measurement",
            "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT",
        ),
        (
            "map_traversal_after_insertion",
            "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT",
        ),
        (
            "accepted_index_checksum",
            "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
            "MATCHED_INPUT_AND_MAP_CONTENT",
        ),
        ("post_update_state_checksum", "FILTER_UPDATE_STAGE_DIVERGED"),
        (
            "map_insertion_batch_ordered_checksum",
            "MAP_INSERTION_STAGE_DIVERGED",
        ),
        ("map_content_after_insertion", "MAP_INSERTION_STAGE_DIVERGED"),
    ),
)
def test_stage_classification_rules(field: str, expected: str) -> None:
    first, second = _rows()
    second[10][field] = 999
    alias_to_snapshot = {
        "map_content_before_measurement": "map_before_content_checksum",
        "map_traversal_before_measurement":
            "map_before_traversal_checksum",
        "map_content_after_insertion": "map_after_content_checksum",
        "map_traversal_after_insertion": "map_after_traversal_checksum",
    }
    if field in alias_to_snapshot:
        second[10][alias_to_snapshot[field]] = 999
    assert compare_pair(first, second)["stage_classification"] == expected


def test_complete_match_classifies_no_divergence() -> None:
    first, second = _rows()
    result = compare_pair(first, second)
    assert result["stage_classification"] == "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR"
    assert result["branch_reproduced"] is False


def test_missing_record_classifies_evidence_gap() -> None:
    first, second = _rows()
    result = compare_pair(first, second[:-1])
    assert result["stage_classification"] == (
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT"
    )
    assert result["evidence_gap"] is True


def test_traversal_difference_does_not_claim_content_difference() -> None:
    first, second = _rows()
    second[0]["map_traversal_before_measurement"] = 999
    second[0]["map_before_traversal_checksum"] = 999
    result = compare_pair(first, second)
    assert result["identity_status"]["map_content_before"] == (
        "MATCHED_BY_CANONICAL_CHECKSUM"
    )
