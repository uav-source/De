from copy import deepcopy
from pathlib import Path

import pytest

from eval.directional_capture_contract import (
    FROZEN_AUDIT_STATUSES,
    FROZEN_PROTOCOL_SEMANTIC_SHA256,
    FROZEN_REGISTRATION_SETTINGS,
    PROTECTED_ARTIFACT_PATHS,
    SCHEMA_VERSION,
    load_capture_range_protocol,
    protocol_semantic_sha256,
    validate_capture_range_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs/capture_range/day1_protocol.yaml"


def _protocol():
    return load_capture_range_protocol(PROTOCOL_PATH)


def test_protocol_loads_and_preserves_final_scientific_audit_state():
    config = _protocol()

    assert config["schema_version"] == SCHEMA_VERSION
    state = config["frozen_scientific_state"]
    for field, expected in FROZEN_AUDIT_STATUSES.items():
        assert state[field] == expected
        assert type(state[field]) is type(expected)
    assert state["SCIENTIFIC_AUDIT_COMPLETE"] is True
    assert state["PRIMARY_AUDIT_CONCLUSION"] == "PILOT_LABEL_INVALIDATED"
    assert tuple(config["protected_artifact_paths"]) == PROTECTED_ARTIFACT_PATHS
    assert protocol_semantic_sha256(config) == FROZEN_PROTOCOL_SEMANTIC_SHA256


def test_product_manifold_and_separate_direction_grids_are_frozen():
    config = _protocol()
    convention = config["pose_perturbation"]

    assert convention["manifold"] == "SO3_right_plus_R3_world_additive"
    assert convention["perturbation_vector_order"] == [
        "delta_theta_body",
        "delta_position_world",
    ]
    assert convention["rotation_update"] == "R_prime = R_ref @ Exp(delta_theta_body)"
    assert convention["translation_update"] == "p_prime = p_ref + delta_position_world"
    assert convention["literal_right_se3_translation_composition_allowed"] is False

    sampling = config["sampling"]
    assert [row["direction_id"] for row in sampling["translation"]["directions"]] == [
        "+x", "-x", "+y", "-y", "+z", "-z",
    ]
    assert sampling["translation"]["amplitudes"] == [0.0, 0.02, 0.05, 0.1, 0.2]
    assert [row["direction_id"] for row in sampling["rotation"]["directions"]] == [
        "+roll", "-roll", "+pitch", "-pitch", "+yaw", "-yaw",
    ]
    assert sampling["rotation"]["amplitude_unit"] == "radian"
    assert sampling["rotation"]["amplitudes_deg"] == [0.0, 0.5, 1.0, 2.0, 5.0]
    assert sampling["rotation"]["amplitudes_rad"] == [
        0.0,
        0.008726646259971648,
        0.017453292519943295,
        0.03490658503988659,
        0.08726646259971647,
    ]
    assert sampling["repeats_per_direction_amplitude"] == 3
    assert sampling["keep_signed_directions_separate"] is True
    assert sampling["keep_translation_and_rotation_separate"] is True


def test_success_probability_and_capture_radius_rules_are_frozen():
    config = _protocol()

    assert config["success"] == {
        "translation_error_threshold_m": 0.02,
        "rotation_geodesic_error_threshold_deg": 0.5,
        "rotation_geodesic_error_threshold_rad": 0.008726646259971648,
        "require_solver_converged": True,
        "require_finite_result": True,
        "require_iteration_limit_not_failed": True,
        "final_residual_only_is_sufficient": False,
        "thresholds_may_be_tuned_from_day1_results": False,
    }
    assert config["recovery_probability"]["definition"] == (
        "successful_trials / total_trials"
    )
    assert config["recovery_probability"]["confidence_interval"] == {
        "method": "wilson",
        "confidence_level": 0.95,
    }
    assert config["recovery_curve"]["fit_method"] == "isotonic_regression"
    assert config["recovery_curve"]["monotonicity"] == "nonincreasing"
    assert config["recovery_curve"]["preserve_raw_probabilities"] is True
    assert config["recovery_curve"]["preserve_nonmonotonic_evidence"] is True
    assert config["capture_radius"]["d50"]["target_probability"] == 0.5
    assert config["capture_radius"]["d90"]["target_probability"] == 0.9
    assert config["capture_radius"]["right_censoring"]["enabled"] is True
    assert config["capture_radius"]["right_censoring"]["censored_value"] is None
    assert config["capture_radius"]["extrapolation_allowed"] is False


def test_executable_registration_randomness_and_no_gt_boundaries_are_frozen():
    config = _protocol()

    assert config["registration"] == FROZEN_REGISTRATION_SETTINGS
    assert config["registration"]["k_neighbors"] == 5
    assert config["registration"]["max_neighbor_distance_m"] == 0.75
    assert config["randomness"]["global_seed"] == 15001
    assert config["randomness"]["include_method_name_in_seed"] is False
    assert config["randomness"]["point_subsampling"] == {
        "enabled": False,
        "retention_fraction": 1.0,
    }
    assert config["randomness"]["range_noise"] == {
        "enabled": False,
        "standard_deviation_m": 0.0,
    }
    assert config["ground_truth_boundary"]["optimizer_forbidden_inputs"] == [
        "ground_truth_weak_direction",
        "pose_gt",
        "axis_gt",
    ]
    assert config["ground_truth_boundary"]["expected_optimizer_gt_access_count"] == 0
    assert config["measurement_object"]["result_is_algorithm_conditioned"] is True
    assert (
        config["measurement_object"]["result_is_algorithm_independent_scene_property"]
        is False
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["frozen_scientific_state"].__setitem__("STAGE2_GATE", "PASS"),
        lambda value: value["success"].__setitem__(
            "translation_error_threshold_m", 0.03
        ),
        lambda value: value["sampling"]["translation"]["directions"].reverse(),
        lambda value: value["capture_radius"]["d90"].__setitem__(
            "target_probability", 0.8
        ),
        lambda value: value["ground_truth_boundary"]["optimizer_forbidden_inputs"].pop(),
        lambda value: value["registration"].__setitem__("max_iterations", 20.0),
        lambda value: value.__setitem__("unregistered_extension", True),
    ],
)
def test_any_semantic_or_type_drift_is_rejected(mutate):
    changed = deepcopy(_protocol())
    mutate(changed)

    with pytest.raises(ValueError):
        validate_capture_range_protocol(changed)


def test_loader_rejects_non_mapping_and_duplicate_yaml_keys(tmp_path):
    non_mapping = tmp_path / "list.yaml"
    non_mapping.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be a mapping"):
        load_capture_range_protocol(non_mapping)

    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        "schema_version: directional_capture_range_day1_protocol_v1\n"
        "schema_version: silently_shadowed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid capture-range protocol YAML"):
        load_capture_range_protocol(duplicate)


def test_validator_rejects_nonfinite_values():
    changed = deepcopy(_protocol())
    changed["registration"]["damping"] = float("nan")

    with pytest.raises(ValueError, match="non-finite"):
        validate_capture_range_protocol(changed)
