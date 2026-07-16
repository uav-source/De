import copy
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from degen_detector.odi_tracker import compute_metrics_for_frame
from fastlio2_adapter.detector_adapter import (
    DETECTOR_RESIDUAL_INPUT_FIELD,
    DETECTOR_STATE_ORDER,
    DETECTOR_TRANSLATION_FRAME,
    PRIOR_COVARIANCE_USED_BY_DETECTOR,
    evaluate_readonly_observation,
    load_production_detector_contract,
    prepare_production_detector_input,
)
from fastlio2_adapter.detector_output_schema import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/42_run_harmful_bias_day4_synthetic_adapter.py"
ADAPTER_PATH = ROOT / "src/fastlio2_adapter/detector_adapter.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("day4_synthetic_runner_adapter", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def observations():
    return load_runner().build_synthetic_observations()


def test_mapping_uses_day3_detector_rows_without_second_reorder(observations):
    record = observations["well_conditioned"]
    mapped = prepare_production_detector_input(record)
    expected = np.asarray(record["detector_pose_jacobian_rows"], dtype=np.float64)
    assert np.array_equal(mapped["jacobian"], expected)
    assert mapped["jacobian"] is not expected
    assert DETECTOR_STATE_ORDER == (
        "delta_theta_x",
        "delta_theta_y",
        "delta_theta_z",
        "delta_p_x",
        "delta_p_y",
        "delta_p_z",
    )
    assert DETECTOR_TRANSLATION_FRAME == "WORLD"
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "DETECTOR_COLUMN_MAP" not in source
    assert "[3, 4, 5, 0, 1, 2]" not in source


def test_scalar_variance_and_residual_mapping_are_exact(observations):
    record = observations["weak_x"]
    mapped = prepare_production_detector_input(record)
    assert mapped["variance"].dtype == np.float64
    assert mapped["variance"].shape == (
        record["valid_correspondence_count"],
    )
    assert np.array_equal(
        mapped["variance"],
        np.full(
            record["valid_correspondence_count"],
            record["measurement_variance_scalar_m2"],
            dtype=np.float64,
        ),
    )
    assert DETECTOR_RESIDUAL_INPUT_FIELD == "formal_filter_innovation_h"
    assert np.array_equal(
        mapped["residual"],
        np.asarray(record["formal_filter_innovation_h"], dtype=np.float64),
    )
    assert np.allclose(
        mapped["residual"],
        -np.asarray(record["signed_geometric_residual_pd2"], dtype=np.float64),
        rtol=0.0,
        atol=1.0e-12,
    )
    assert PRIOR_COVARIANCE_USED_BY_DETECTOR is False
    assert "prior_covariance_detector_order" not in ADAPTER_PATH.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "fixture_id", ["well_conditioned", "weak_x", "weak_rotated"]
)
def test_adapter_is_exactly_equivalent_to_direct_production_call(
    observations, fixture_id
):
    record = observations[fixture_id]
    adapter_output = evaluate_readonly_observation(record)
    direct = direct_production_output(record)
    scalar_fields = (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "primary_eigengap_ratio",
    )
    for field in scalar_fields:
        assert abs(adapter_output[field] - direct[field]) <= 1.0e-12
    assert np.allclose(
        adapter_output["translation_eigenvalues_ascending"],
        direct["translation_eigenvalues_ascending"],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert np.allclose(
        adapter_output["primary_weak_direction"],
        direct["primary_weak_direction"],
        rtol=0.0,
        atol=1.0e-12,
    )
    for field in (
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
    ):
        assert adapter_output[field] is direct[field]


@pytest.mark.parametrize(
    "fixture_id", ["well_conditioned", "weak_x", "weak_rotated"]
)
def test_adapter_does_not_mutate_any_observation_payload(observations, fixture_id):
    record = copy.deepcopy(observations[fixture_id])
    before = copy.deepcopy(record)
    before_sha = canonical_sha256(record)
    evaluate_readonly_observation(record)
    assert canonical_sha256(record) == before_sha
    assert record == before
    for field in (
        "detector_pose_jacobian_rows",
        "signed_geometric_residual_pd2",
        "formal_filter_innovation_h",
        "measurement_variance_scalar_m2",
        "prior_position_world",
        "prior_covariance_detector_order",
        "accepted_source_indices",
        "correspondence_proxy_ids",
        "plane_parameters_world",
        "ordered_neighbor_coordinates_world",
    ):
        assert record[field] == before[field]


@pytest.mark.parametrize(
    "fixture_id", ["well_conditioned", "weak_x", "weak_rotated"]
)
def test_three_adapter_calls_are_byte_deterministic(observations, fixture_id):
    outputs = [
        evaluate_readonly_observation(observations[fixture_id]) for _ in range(3)
    ]
    checksums = [canonical_sha256(output) for output in outputs]
    assert checksums[0] == checksums[1] == checksums[2]
    assert outputs[0] == outputs[1] == outputs[2]


def test_synthetic_weak_directions_match_fixture_expectations(observations):
    weak_x = evaluate_readonly_observation(observations["weak_x"])
    weak_rotated = evaluate_readonly_observation(observations["weak_rotated"])
    assert abs(float(weak_x["primary_weak_direction"][0])) >= 0.999
    expected = np.asarray([1.0, 1.0, 0.0]) / math.sqrt(2.0)
    assert (
        abs(
            float(
                np.dot(
                    np.asarray(weak_rotated["primary_weak_direction"]),
                    expected,
                )
            )
        )
        >= 0.995
    )


def test_too_few_correspondences_return_explicit_invalid_output(observations):
    record = copy.deepcopy(observations["well_conditioned"])
    row_fields = (
        "detector_pose_jacobian_rows",
        "signed_geometric_residual_pd2",
        "formal_filter_innovation_h",
        "accepted_source_indices",
        "correspondence_proxy_ids",
        "plane_parameters_world",
        "ordered_neighbor_coordinates_world",
    )
    for field in row_fields:
        record[field] = record[field][:5]
    record["valid_correspondence_count"] = 5
    output = evaluate_readonly_observation(record)
    assert output["valid"] is False
    assert output["invalid_reason"] == "TOO_FEW_CORRESPONDENCES"
    assert output["primary_weak_direction"] is None


def test_frozen_detector_contract_matches_source_config_and_lock():
    config, provenance = load_production_detector_contract()
    assert provenance == {
        "detector_metric_version": "detector_stage2a_v1",
        "detector_source_sha256": "c515e5321e569ed074ae1c4f33563e73a82775800f20197612c2816086676d17",
        "detector_config_sha256": "665c3df8f794841ac5f3afe97e77f9993aaae2feaf3510043ecff6646acf2398",
        "detector_lock_sha256": "075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358",
    }
    assert config["odi_trigger_threshold"] == pytest.approx(
        0.035199792993590634, rel=0.0, abs=0.0
    )


def direct_production_output(record):
    jacobian = np.asarray(record["detector_pose_jacobian_rows"], dtype=np.float64)
    variance = np.full(
        jacobian.shape[0],
        record["measurement_variance_scalar_m2"],
        dtype=np.float64,
    )
    config, _ = load_production_detector_contract()
    metrics = compute_metrics_for_frame(jacobian, variance, config)
    return {
        "odi_trans": float(metrics["ODI_trans"]),
        "ais_trans": float(metrics["AIS_trans_normalized"]),
        "lambda_min_trans": float(metrics["lambda_min_trans_normalized"]),
        "condition_number_trans": float(metrics["condition_number_trans"]),
        "translation_eigenvalues_ascending": sorted(
            [
                metrics["trans_eig_1"],
                metrics["trans_eig_2"],
                metrics["trans_eig_3"],
            ]
        ),
        "primary_weak_direction": [
            metrics["primary_weak_dir_x"],
            metrics["primary_weak_dir_y"],
            metrics["primary_weak_dir_z"],
        ],
        "primary_eigengap_ratio": float(metrics["primary_eigengap_ratio"]),
        "primary_direction_stable": bool(metrics["primary_direction_stable"]),
        "degeneracy_triggered": bool(metrics["degeneracy_triggered"]),
        "actionable_direction": bool(metrics["actionable_direction"]),
    }
