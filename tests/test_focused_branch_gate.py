from __future__ import annotations

from fastlio2_adapter.focused_branch_stage_localization import (
    focused_run_completeness,
    localization_gate,
)


def semantic_rows():
    return [
        {
            "pair": f"pair-{index}",
            "semantic_mismatch_count": 1,
            "first_divergence_scan": 164,
        }
        for index in range(6)
    ]


def stage_rows(classification=None):
    value = classification or (
        "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
        "MATCHED_INPUT_AND_MAP_CONTENT"
    )
    return [
        {
            "pair": f"pair-{index}",
            "comparison_pass": True,
            "stage_classification_complete": True,
            "previous_scan_identity_pass": True,
            "formal_branch_reproduced": True,
            "first_formal_divergence_scan": 164,
            "stage_classification": value,
        }
        for index in range(6)
    ]


def test_complete_correspondence_localization_recommends_day7() -> None:
    result = localization_gate(
        run_complete=[True] * 4,
        semantic=semantic_rows(),
        stage=stage_rows(),
    )
    assert result["formal_branch_reproduced"] is True
    assert result["formal_branch_stage_localized"] is True
    assert result["day7_recommended"] is True
    assert result["day7_authorized"] is False


def test_outside_window_fails_localization() -> None:
    semantic = semantic_rows()
    semantic[0]["first_divergence_scan"] = 220
    result = localization_gate(
        run_complete=[True] * 4,
        semantic=semantic,
        stage=stage_rows(),
    )
    assert result["formal_branch_stage_localized"] is False
    assert result["day7_recommended"] is False


def test_missing_previous_identity_fails_execution() -> None:
    stage = stage_rows()
    stage[0]["previous_scan_identity_pass"] = False
    result = localization_gate(
        run_complete=[True] * 4,
        semantic=semantic_rows(),
        stage=stage,
    )
    assert result[
        "focused_formal_branch_localization_execution_pass"
    ] is False


def test_focused_run_completeness_contract() -> None:
    summary = {
        "wrapper_exit_code": 0,
        "lidar_callback_count": 491,
        "imu_callback_count": 9953,
        "runtime_scan_count": 490,
        "observation_record_count": 487,
        "stage_hash_record_count": 51,
        "stage_hash_first_scan": 155,
        "stage_hash_last_scan": 205,
        "map_before_snapshot_count": 51,
        "map_after_snapshot_count": 51,
        "coherent_snapshot_count": 102,
        "incoherent_snapshot_count": 0,
        "cross_scan_continuity_violation_count": 0,
        "map_snapshot_cross_scan_coherence_pass": True,
        "tap_drop_count": 0,
        "writer_error_count": 0,
        "binary_checksum_failure_count": 0,
        "truncated_record_count": 0,
        "extra_trailing_bytes": 0,
        "in_call_mutation_count": 0,
        "diagnostic_mutation_count": 0,
        "schema_rejected_record_count": 0,
        "GT_TOPIC_CONSUMED_COUNT": 0,
        "end_of_stream_drain_pass": True,
        "normal_shutdown_pass": True,
        "runtime_product_pass": True,
        "adjudicated_tail_handoff_pass": True,
        "complete": True,
    }
    assert focused_run_completeness(summary)["run_completeness_pass"]

