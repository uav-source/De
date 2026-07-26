import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from eval.day5_v5_adjudication import (
    EXPECTED_V5_AUDIT_SHA256,
    adjudicate_archive,
    adjudicate_executed_run,
    full_matrix_status,
    recalculate_tail_clock,
    sha256_file,
    write_outputs,
)


def _handoff():
    return {
        "last_bag_clock_ns": 100,
        "tail_first_clock_ns": 110,
        "tail_clock_step_ns": 10,
        "tail_publish_count": 4,
        "tail_final_clock_ns": 140,
        "clock_backward_count": 0,
        "clock_duplicate_count": 9,
        "clock_publisher_overlap_count": 0,
        "start_success": True,
        "stop_success": True,
        "failure_reason": "NONE",
    }


def _recalculation(handoff=None):
    return recalculate_tail_clock(handoff or _handoff(), True)


def _gate_inputs():
    return {
        "mixed_counter_confirmed": True,
        "recalculation": _recalculation(),
        "handoff": _handoff(),
        "drain": {
            "actual_lidar_callback_count": 3,
            "actual_imu_callback_count": 5,
            "actual_last_lidar_header_stamp_ns": 30,
            "actual_last_imu_header_stamp_ns": 50,
            "drain_pass": True,
            "failure_classification": "NONE",
            "main_loop_heartbeat_start": 10,
            "main_loop_heartbeat_end": 11,
        },
        "endpoint_contract": {
            "sequences": [
                {
                    "sequence_id": "avia_quick_shack",
                    "expected_lidar_message_count": 3,
                    "expected_imu_message_count": 5,
                    "last_lidar_header_stamp_ns": 30,
                    "last_imu_header_stamp_ns": 50,
                }
            ]
        },
        "shutdown": {
            "shutdown_completed": True,
            "forced_kill_used": False,
            "forced_terminate_used": False,
            "laser_mapping_exit_code": 0,
            "roslaunch_exit_code": 0,
        },
        "runtime_summary": {
            "runtime_audit_enabled": True,
            "runtime_audit_record_count": 4,
            "writer_error_count": 0,
            "nonfinite_count": 0,
            "final_map_summary_written": True,
        },
        "final_map_summary": {
            "valid": True,
            "final_map_point_count": 2,
            "nonfinite_count": 0,
        },
        "tap_export_summary": {"writer_error_count": 0},
    }


def test_first_and_final_tail_formulas_are_exact():
    result = _recalculation()
    assert result["TAIL_FIRST_FORMULA_PASS"] is True
    assert result["tail_first_clock_difference_ns"] == 0
    assert result["TAIL_FINAL_FORMULA_PASS"] is True
    assert result["tail_final_clock_difference_ns"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("clock_backward_count", 1),
        ("clock_publisher_overlap_count", 1),
        ("tail_first_clock_ns", 111),
        ("tail_final_clock_ns", 141),
    ],
)
def test_invalid_tail_boundary_or_counter_cannot_be_corrected(field, value):
    handoff = _handoff()
    handoff[field] = value
    inputs = _gate_inputs()
    inputs["handoff"] = handoff
    inputs["recalculation"] = _recalculation(handoff)
    result = adjudicate_executed_run(**inputs)
    assert result["EXECUTED_RUN_GATE_CORRECTION_PASS"] is False
    assert result["CORRECTED_EXECUTED_RUN_RESULT"] == "FAIL"


def test_drain_failure_cannot_be_corrected():
    inputs = _gate_inputs()
    inputs["drain"]["drain_pass"] = False
    result = adjudicate_executed_run(**inputs)
    assert result["EXECUTED_RUN_END_OF_STREAM_DRAIN_PASS"] is False
    assert result["EXECUTED_RUN_GATE_CORRECTION_PASS"] is False


def test_incomplete_callbacks_cannot_be_corrected():
    inputs = _gate_inputs()
    inputs["drain"]["actual_lidar_callback_count"] = 2
    result = adjudicate_executed_run(**inputs)
    assert result["EXECUTED_RUN_ALL_CALLBACKS_RECEIVED_PASS"] is False
    assert result["EXECUTED_RUN_GATE_CORRECTION_PASS"] is False


def test_abnormal_shutdown_cannot_be_corrected():
    inputs = _gate_inputs()
    inputs["shutdown"]["shutdown_completed"] = False
    result = adjudicate_executed_run(**inputs)
    assert result["EXECUTED_RUN_NORMAL_SHUTDOWN_PASS"] is False
    assert result["EXECUTED_RUN_GATE_CORRECTION_PASS"] is False


def test_one_of_six_runs_is_not_repeatability_pass():
    result = full_matrix_status()
    assert result["FULL_MATRIX_REPLAY_COUNT"] == 1
    assert result["FULL_MATRIX_REQUIRED_REPLAY_COUNT"] == 6
    assert result["PAIR_COMPARISON_COUNT"] == 0
    assert result["FULL_MATRIX_STATUS"] == "NOT_EVALUATED"
    assert result["QUICK_BASELINE_REPEATABILITY_PASS"] is False
    assert result["OUTDOOR_BASELINE_REPEATABILITY_PASS"] is False
    assert result["BASELINE_REPEATABILITY_PASS"] is False
    assert result["DAY5_STARTUP_SYNC_V5_PASS"] is False


def test_frozen_archive_is_not_modified_and_outputs_are_deterministic(tmp_path):
    archive = (
        Path.home()
        / "Degen-LIO-multihyp-D5-startup-sync-v5-audit.tar.gz"
    )
    if not archive.is_file():
        pytest.skip("full frozen V5 archive is not part of external overlay")
    before = sha256_file(archive)
    assert before == EXPECTED_V5_AUDIT_SHA256
    result = adjudicate_archive(archive)
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_outputs(result, first)
    write_outputs(deepcopy(result), second)
    first_files = sorted(path.relative_to(first) for path in first.iterdir())
    second_files = sorted(path.relative_to(second) for path in second.iterdir())
    assert first_files == second_files
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
    assert sha256_file(archive) == before
    assert hashlib.sha256((first / "SHA256SUMS").read_bytes()).hexdigest()
