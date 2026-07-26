from __future__ import annotations

from fastlio2_adapter.bounded_branch_reproduction import (
    branch_gate,
    run_completeness,
)


def _semantic(count: int = 0):
    return [
        {"pair": f"pair-{index}", "semantic_mismatch_count": count}
        for index in range(6)
    ]


def _stage(*, formal: bool = False):
    return [
        {
            "pair": f"pair-{index}",
            "comparison_pass": True,
            "stage_classification_complete": True,
            "formal_branch_reproduced": formal,
            "first_formal_divergence_stage":
                "correspondence" if formal else "NONE",
            "evidence_gap": False,
        }
        for index in range(6)
    ]


def test_four_complete_equal_runs_pass_execution_but_not_formal_gate() -> None:
    result = branch_gate(
        run_complete=[True] * 4,
        semantic_summaries=_semantic(),
        stage_summaries=_stage(),
    )
    assert result["bounded_branch_reproduction_execution_pass"] is True
    assert result["formal_branch_reproduced"] is False
    assert result["branch_reproduction_status"] == (
        "NOT_OBSERVED_IN_FOUR_FIXED_RUNS"
    )


def test_formal_mismatch_requires_matching_stage_localization() -> None:
    result = branch_gate(
        run_complete=[True] * 4,
        semantic_summaries=_semantic(1),
        stage_summaries=_stage(formal=True),
    )
    assert result["formal_branch_reproduced"] is True
    assert result["formal_branch_stage_localized"] is True


def test_evidence_gap_fails_closed() -> None:
    stage = _stage(formal=True)
    stage[0]["comparison_pass"] = False
    stage[0]["evidence_gap"] = True
    result = branch_gate(
        run_complete=[True] * 4,
        semantic_summaries=_semantic(1),
        stage_summaries=stage,
    )
    assert result["bounded_branch_reproduction_execution_pass"] is False
    assert result["formal_branch_reproduced"] is False


def test_run_completeness_requires_wrapper_zero_and_all_counts() -> None:
    summary = {
        "wrapper_exit_code": 0,
        "lidar_callback_count": 491,
        "imu_callback_count": 9953,
        "runtime_scan_count": 490,
        "observation_record_count": 487,
        "stage_hash_record_count": 26,
        "stage_hash_first_scan": 135,
        "stage_hash_last_scan": 160,
        "map_before_snapshot_count": 26,
        "map_after_snapshot_count": 26,
        "coherent_snapshot_count": 52,
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
    assert run_completeness(summary)["run_completeness_pass"] is True
    summary["wrapper_exit_code"] = 1
    assert run_completeness(summary)["run_completeness_pass"] is False

