import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("startup_gate", ROOT / "scripts/50_run_day5_startup_sync_matrix.py")
M = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(M)


REQUIRED = (
    "clip_lock_pass", "connection_handshake_pass", "paused_start_pass",
    "runtime_output_contract_pass", "runtime_allowlist_pass",
    "runtime_output_absolute_path_pass", "runtime_binary_completeness_pass",
    "startup_input_boundary_pass", "source_lock_pass",
    "binary_lock_pass", "parameter_identity_pass", "scan_pairing_pass",
    "measure_group_equivalence_pass", "pose_equivalence_pass",
    "covariance_equivalence_pass", "jacobian_equivalence_pass",
    "residual_equivalence_pass", "accepted_index_equivalence_pass",
    "correspondence_equivalence_pass", "map_size_equivalence_pass",
    "final_map_equivalence_pass", "no_nonfinite_pass", "no_gt_runtime_pass",
)


def passing():
    return {
        **{key: True for key in REQUIRED},
        "successful_replay_count": 6,
        "executed_replay_count": 6,
        "evaluated_pair_count": 6,
        "executed_handshake_pass_count": 6,
        "executed_paused_start_pass_count": 6,
        "executed_runtime_product_pass_count": 6,
    }


def test_complete_stage_a_pass_authorizes_only_capture_export_remediation():
    result = M.evaluate_startup_sync_v3_gate(passing())
    assert result["BASELINE_REPEATABILITY_PASS"] is True
    assert result["CONNECTION_HANDSHAKE_STATUS"] == "PASS"
    assert result["DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED"] is True
    assert result["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert result["DAY5_RUNTIME_EQUIVALENCE_PASS"] is False


def test_first_measure_group_difference_fails():
    values = passing(); values["startup_input_boundary_pass"] = False
    result = M.evaluate_startup_sync_v3_gate(values)
    assert result["DAY5_STARTUP_SYNC_V3_PASS"] is False
    assert result["STARTUP_INPUT_BOUNDARY_STATUS"] == "FAIL"


def test_scan_pairing_failure_fails_complete_matrix():
    values = passing(); values["scan_pairing_pass"] = False
    result = M.evaluate_startup_sync_v3_gate(values)
    assert result["BASELINE_REPEATABILITY_PASS"] is False
    assert result["SCAN_PAIRING_STATUS"] == "FAIL"


def test_all_six_pairs_are_required():
    values = passing(); values["evaluated_pair_count"] = 5
    result = M.evaluate_startup_sync_v3_gate(values)
    assert result["BASELINE_REPEATABILITY_PASS"] is False
    assert result["SCAN_PAIRING_STATUS"] == "NOT_EVALUATED"


def test_one_of_six_runs_cannot_produce_full_matrix_pass():
    values = passing()
    values.update(
        successful_replay_count=1,
        evaluated_pair_count=0,
        executed_handshake_pass_count=1,
        executed_paused_start_pass_count=1,
    )
    result = M.evaluate_startup_sync_v3_gate(values)
    assert result["executed_run_handshake_pass_count"] == 1
    assert result["CONNECTION_HANDSHAKE_STATUS"] == "NOT_EVALUATED"
    assert result["DAY5_STARTUP_SYNC_V3_PASS"] is False


def test_scan_index_shift_cannot_be_used_for_alignment():
    rows = []
    for sequence in M.SEQUENCES:
        for repeat in (1, 2, 3):
            rows.append(
                {
                    "sequence_id": sequence,
                    "scan_count": 10,
                    "first_runtime_scan_index": 0,
                    "first_measure_group_checksum": 1,
                    "first_measure_group_lidar_begin_time": 1.0,
                    "first_measure_group_lidar_end_time": 2.0,
                    "first_measure_group_lidar_point_count": 3,
                    "first_measure_group_imu_message_count": 4,
                    "first_measure_group_first_imu_timestamp": 1.1,
                    "first_measure_group_last_imu_timestamp": 1.9,
                    "first_ten_signature_sha256": "same" if repeat < 3 else "shifted",
                }
            )
    assert M.startup_boundary_pass(rows) is False
