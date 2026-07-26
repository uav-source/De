import copy
import math

import pytest

from fastlio2_adapter.runtime_equivalence import (
    combine_equivalence_results,
    compare_final_maps,
    compare_parameter_documents,
    compare_runtime_rows,
    quaternion_geodesic_difference,
    runtime_overhead,
)


def row(scan_index=0):
    value = {
        "sequence_id": "avia_quick_shack",
        "scan_index": scan_index,
        "timestamp_begin": float(scan_index),
        "timestamp_end": float(scan_index) + 0.1,
        "update_invoked": True,
        "first_valid_linearization_found": True,
        "skip_reason": "NONE",
        "measurement_call_count": 2,
        "valid_measurement_call_count": 2,
        "downsampled_point_count": 100,
        "valid_correspondence_count": 50,
        "posterior_position": [1.0, 2.0, 3.0],
        "posterior_orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "posterior_covariance_native_flat": [0.0] * (23 * 23),
        "map_size_after_update": 1000,
        "lidar_point_count": 100,
        "imu_message_count": 20,
        "first_imu_timestamp": float(scan_index),
        "last_imu_timestamp": float(scan_index) + 0.09,
        "lidar_begin_time": float(scan_index),
        "lidar_end_time": float(scan_index) + 0.1,
        "scan_total_runtime_ns": 1_000_000,
        "tap_capture_ns": 1000,
        "binary_writer_ns": 2000,
    }
    for name in (
        "prior_state_checksum",
        "prior_covariance_checksum",
        "posterior_state_checksum",
        "posterior_covariance_checksum",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
        "measure_group_checksum",
    ):
        value[name] = 123
    return value


def test_comparator_accepts_identical_rows_and_quaternion_sign():
    left = [row(0), row(1)]
    right = copy.deepcopy(left)
    summary, mismatch = compare_runtime_rows(left, right, comparison_id="pair")
    assert summary["runtime_equivalence_pass"] is True
    assert "pass" not in summary
    assert not mismatch
    assert quaternion_geodesic_difference([0, 0, 0, 1], [0, 0, 0, -1]) == 0


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(posterior_state_checksum=999),
        lambda value: value["posterior_position"].__setitem__(0, 1.0 + 2e-12),
        lambda value: value["posterior_covariance_native_flat"].__setitem__(0, 2e-12),
        lambda value: value.update(map_size_after_update=999),
    ],
)
def test_comparator_rejects_checksum_pose_covariance_or_map_change(mutation):
    left = [row(0)]
    right = copy.deepcopy(left)
    mutation(right[0])
    summary, mismatch = compare_runtime_rows(left, right, comparison_id="pair")
    assert summary["runtime_equivalence_pass"] is False
    assert mismatch


def test_comparator_detects_missing_and_duplicate_scans():
    summary, _ = compare_runtime_rows([row(0), row(1)], [row(0)], comparison_id="x")
    assert summary["missing_scan_count"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        compare_runtime_rows([row(0), row(0)], [row(0)], comparison_id="x")


def test_final_map_checksum_and_size_are_both_required():
    base = {
        "final_map_point_count": 2,
        "final_map_checksum": 5,
        "map_checksum_algorithm": "FNV1A64_SORTED_FLOAT32_XYZI_V1",
    }
    assert compare_final_maps(base, base)["final_map_equivalence_pass"] is True
    changed = dict(base, final_map_checksum=6)
    assert compare_final_maps(base, changed)["final_map_equivalence_pass"] is False


def test_parameter_allowlist_is_fail_closed():
    left = {"harmful_bias": {"run_id": "off", "runtime_mode": "AUDIT_ONLY"}, "max_iteration": 3}
    right = {"harmful_bias": {"run_id": "on", "runtime_mode": "CAPTURE_ONLY"}, "max_iteration": 3}
    assert compare_parameter_documents(left, right)["parameter_diff_allowlist_pass"] is True
    right["max_iteration"] = 4
    assert compare_parameter_documents(left, right)["parameter_diff_allowlist_pass"] is False


def test_overhead_is_gated_per_input_pair_and_requires_post_warmup_rows():
    off = [row(index) for index in range(25)]
    on = copy.deepcopy(off)
    for value in on:
        value["scan_total_runtime_ns"] = 1_100_000
    summary = runtime_overhead(off, on)
    assert summary["measured_scan_count"] == 5
    assert summary["runtime_hard_gate"] is True
    assert summary["runtime_target_gate"] is False
    with pytest.raises(ValueError, match="too few"):
        runtime_overhead(off[:20], on[:20])


def test_runtime_and_map_results_never_overwrite_each_other():
    runtime_fail = {"runtime_equivalence_pass": False, "first_divergence_stage": "POSTERIOR_STATE", "first_divergence_scan_index": 3}
    runtime_pass = {"runtime_equivalence_pass": True, "first_divergence_stage": "NONE", "first_divergence_scan_index": None}
    map_pass = {"final_map_equivalence_pass": True}
    map_fail = {"final_map_equivalence_pass": False}
    assert combine_equivalence_results(runtime_fail, map_pass)["overall_equivalence_pass"] is False
    assert combine_equivalence_results(runtime_pass, map_fail)["overall_equivalence_pass"] is False
    assert combine_equivalence_results(runtime_pass, map_pass)["overall_equivalence_pass"] is True
    assert combine_equivalence_results(runtime_pass, map_fail)["first_divergence_stage"] == "FINAL_MAP"


def test_stable_quaternion_formula_and_raw_checksum_mismatch_are_separate():
    assert quaternion_geodesic_difference([0, 0, 0, 1], [0, 0, 0, 1]) == 0
    assert quaternion_geodesic_difference([0, 0, 0, 1], [0, 0, 0, -1]) == 0
    angle = quaternion_geodesic_difference([0, 0, 0, 1], [0, 0, 2**-30, 1])
    assert 0 < angle < 1e-8
    assert quaternion_geodesic_difference(
        [0, 0, 0, 1], [0, 0, 2**-0.5, 2**-0.5]
    ) == pytest.approx(math.pi / 4)
    left = [row(0)]
    right = copy.deepcopy(left)
    right[0]["posterior_state_checksum"] += 1
    right[0]["posterior_orientation_xyzw"] = [0, 0, 0, -1]
    summary, _ = compare_runtime_rows(left, right, comparison_id="raw")
    assert summary["max_rotation_geodesic_difference_rad"] == 0
    assert summary["runtime_equivalence_pass"] is False


@pytest.mark.parametrize(
    ("field", "stage"),
    [
        ("measure_group_checksum", "INPUT_GROUP"),
        ("prior_state_checksum", "PRIOR_STATE"),
        ("prior_covariance_checksum", "PRIOR_COVARIANCE"),
        ("formal_native_jacobian_checksum", "FORMAL_LINEARIZATION"),
        ("posterior_state_checksum", "POSTERIOR_STATE"),
        ("posterior_covariance_checksum", "POSTERIOR_COVARIANCE"),
        ("map_size_after_update", "MAP_SIZE"),
    ],
)
def test_first_divergence_stage_order(field, stage):
    left = [row(0)]
    right = copy.deepcopy(left)
    right[0][field] += 1
    summary, _ = compare_runtime_rows(left, right, comparison_id=field)
    assert summary["first_divergence_scan_index"] == 0
    assert summary["first_divergence_stage"] == stage
