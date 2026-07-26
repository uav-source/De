from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DAY1_PROTOCOL = ROOT / "configs/capture_range/day1_protocol.yaml"
DAY2_PROTOCOL = ROOT / "configs/capture_range/day2_synthetic_locked.yaml"


def _load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    assert isinstance(value, dict)
    return value


def test_day2_protocol_has_the_complete_frozen_schema():
    protocol = _load(DAY2_PROTOCOL)

    assert set(protocol) == {
        "protocol",
        "inheritance",
        "randomness",
        "splits",
        "coordinate_contract",
        "direction_set",
        "amplitudes",
        "scene_generator",
        "weak_direction_extraction",
        "capture_radius_aggregation",
        "repeatability",
        "right_censoring_rules",
        "rich_room_pseudo_weak_rule",
        "linear_metrics",
        "full_vs_frozen_value_gate",
        "nonequivalence_candidate_search",
        "monotonicity_audit",
        "day2_gates",
        "outputs",
        "permissions",
    }
    assert protocol["protocol"]["name"] == (
        "directional_capture_range_day2_synthetic_survival_test"
    )
    assert protocol["protocol"]["version"] == "1.0.0"
    assert protocol["protocol"]["status"] == (
        "prospectively_frozen_before_any_day2_run"
    )
    assert protocol["protocol"]["forbid_day2_execution_before_lock_commit"] is True
    assert protocol["protocol"]["forbid_test_seed_consumption_before_test_lock"] is True


def test_day1_measurement_and_success_contract_is_inherited_without_drift():
    day1 = _load(DAY1_PROTOCOL)
    day2 = _load(DAY2_PROTOCOL)
    inherited = day2["inheritance"]

    assert inherited["inherit_day1_measurement_contract"] is True
    assert inherited["inherit_day1_registration_configuration"] is True
    assert inherited["inherit_day1_success_thresholds"] is True
    assert inherited["translation_success_threshold_m"] == (
        day1["success"]["translation_error_threshold_m"]
    ) == 0.02
    assert inherited["rotation_success_threshold_deg"] == (
        day1["success"]["rotation_geodesic_error_threshold_deg"]
    ) == 0.5
    assert inherited["recovery_probability_confidence_level"] == 0.95
    assert inherited["recovery_probability_interval"] == "wilson"
    assert inherited["capture_curve_fit"] == "weighted_nonincreasing_isotonic"
    assert inherited["d50_definition"] == (
        "first_sampled_amplitude_with_fitted_probability_le_0p5"
    )
    assert inherited["d90_definition"] == (
        "first_sampled_amplitude_with_fitted_probability_le_0p9"
    )
    assert inherited["interpolation"] == "forbidden"
    assert inherited["extrapolation"] == "forbidden"
    assert inherited["preserve_raw_probabilities"] is True
    assert inherited["positive_negative_directions_separate"] is True
    assert inherited["translation_rotation_groups_separate"] is True


def test_frozen_splits_directions_amplitudes_and_scenes_are_complete():
    protocol = _load(DAY2_PROTOCOL)
    splits = protocol["splits"]

    assert splits["development"] == {
        "geometry_seeds": [1101, 1103, 1107],
        "measurement_seeds": [2101, 2111],
        "repeats_per_direction_amplitude": 5,
    }
    assert splits["test"] == {
        "geometry_seeds": [1201, 1213, 1223],
        "measurement_seeds": [2203, 2213],
        "repeats_per_direction_amplitude": 10,
    }
    assert set(splits["development"]["geometry_seeds"]).isdisjoint(
        splits["test"]["geometry_seeds"]
    )
    assert set(splits["development"]["measurement_seeds"]).isdisjoint(
        splits["test"]["measurement_seeds"]
    )
    assert splits["require_disjoint_geometry_seeds"] is True
    assert splits["require_disjoint_measurement_seeds"] is True

    directions = protocol["direction_set"]
    assert len(directions["base_directed_axes"]) == 6
    assert len(directions["supplemental_sphere"]["raw_vectors"]) == 12
    assert directions["normalization_required"] is True
    assert directions["generate_inventory_before_development"] is True
    assert directions["freeze_inventory_sha256_before_development"] is True
    assert protocol["coordinate_contract"]["do_not_merge_antipodal_directions"] is True
    assert protocol["amplitudes"]["translation_m"] == [
        0.00, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80,
    ]
    assert protocol["amplitudes"]["rotation_deg"] == [
        0.00, 0.25, 0.50, 1.00, 2.00, 5.00, 10.00, 20.00,
    ]

    scenes = protocol["scene_generator"]
    assert set(scenes) == {
        "common",
        "geometry_rich_room",
        "long_corridor",
        "parallel_walls",
        "end_face_transition",
        "repeated_structure",
    }
    assert set(scenes["end_face_transition"]["variants"]) == {
        "PRESENT", "WEAK", "ABSENT",
    }


def test_frozen_statistics_gates_outputs_and_prohibitions_are_explicit():
    protocol = _load(DAY2_PROTOCOL)

    assert protocol["repeatability"]["bootstrap_repetitions"] == 2000
    assert protocol["repeatability"]["bootstrap_seed"] == 271828
    assert protocol["right_censoring_rules"] == {
        "never_replace_with_maximum_amplitude_as_exact_value": True,
        "never_extrapolate": True,
        "full_vs_frozen_numeric_relative_difference_requires_both_exact": True,
        "if_one_exact_one_censored": {
            "report_categorical_order_only": True,
            "allow_probability_curve_gap_gate": True,
        },
        "if_both_censored": {
            "numeric_difference": None,
            "categorical_result": "both_right_censored",
        },
    }
    gates = protocol["day2_gates"]
    assert set(gates) == {
        "engineering",
        "directionality",
        "geometry_rich_control",
        "full_reassociation_value",
        "preliminary_repeatability",
        "day3_authorization",
    }
    assert gates["directionality"] == {
        "long_corridor_median_angle_error_deg_max": 10.0,
        "parallel_walls_median_angle_error_deg_max": 10.0,
        "minimum_number_of_degraded_scenes_with_separation_pass": 2,
        "separation_ratio_lower_bound_min": 0.30,
    }
    assert len(protocol["outputs"]["required_tables"]) == 15
    assert protocol["outputs"]["required_files"] == [
        "protocol_lock.json",
        "direction_inventory_lock.json",
        "day2_test_lock.json",
        "run_manifest.json",
        "day2_report.md",
        "final_decision.json",
        "SHA256SUMS",
    ]
    assert len(protocol["permissions"]) == 15
    assert all(value is False for value in protocol["permissions"].values())
