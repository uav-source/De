from pathlib import Path

from capture_range.day2_protocol import load_effective_day2_protocol


ROOT = Path(__file__).resolve().parents[1]


def test_axis_aligned_grid_sampling_and_checksum_semantics_are_frozen():
    semantics = load_effective_day2_protocol(ROOT).amendment[
        "scene_generation_semantics"
    ]

    assert semantics["coordinate_bounds"] == {
        "room_and_corridor_centered_at_world_origin_xy": True,
        "floor_z_m": 0.0,
        "ceiling_z_m_equals_scene_height": True,
        "corridor_x_bounds_formula": ("-length_over_2", "length_over_2"),
        "room_x_bounds_formula": ("-length_over_2", "length_over_2"),
        "room_y_bounds_formula": ("-width_over_2", "width_over_2"),
    }
    sampling = semantics["planar_surface_sampling"]
    assert sampling["algorithm"] == "inclusive_regular_grid_with_seeded_phase_then_clip"
    assert sampling["coordinate_formula"] == "min_value_plus_phase_plus_k_times_spacing"
    assert sampling["phase_range"] == "[0, spacing)"
    assert sampling["phase_key_fields"] == (
        "geometry_seed", "scene_id", "scene_variant", "primitive_id",
        "map_or_scan", "surface_axis_name",
    )
    assert sampling["quantization_for_checksums_m"] == 1.0e-9
    assert sampling["deduplicate_rule"] == (
        "deduplicate_only_equal_quantized_position_and_equal_normal"
    )
    assert sampling["retain_same_position_with_different_normals"] is True
    assert sampling["deterministic_lexicographic_sort_before_checksum"] is True
    assert semantics["cuboid_sampling"]["sample_all_six_faces"] is True


def test_map_scan_seed_domains_and_synthetic_sensor_limit_are_frozen():
    semantics = load_effective_day2_protocol(ROOT).amendment[
        "scene_generation_semantics"
    ]

    assert semantics["map_generation"] == {
        "sample_from_scene_primitives_independently_of_scan": True,
        "spacing_m_source": "v1_0_scene_generator_common_map_point_spacing_m",
        "retain_points_within_reference_position_range_m": 20.0,
    }
    assert semantics["scan_generation"] == {
        "sample_same_scene_primitives_with_independent_scan_phase": True,
        "spacing_m_source": "v1_0_scene_generator_common_scan_point_spacing_m",
        "transform_world_points_to_reference_sensor_frame": True,
        "range_filter_m": {"minimum": 0.30, "maximum": 20.0},
        "field_of_view": "full_360_degree_synthetic_no_occlusion_model",
        "explicit_limitation": "day2_does_not_model_ray_occlusion_or_lidar_scan_pattern",
    }
    assert semantics["geometry_seed_effects"] == (
        "map_grid_phase", "scan_grid_phase", "end_face_retention_hash",
        "repeated_rib_longitudinal_phase",
    )
    assert semantics["measurement_seed_effects"] == (
        "scan_gaussian_noise", "map_gaussian_noise", "scan_dropout",
    )
    assert semantics["forbidden_seed_effects"] == (
        "scene_dimensions", "theoretical_weak_direction", "reference_pose",
        "success_thresholds",
    )


def test_end_face_ribs_and_required_snapshot_checksums_are_frozen():
    semantics = load_effective_day2_protocol(ROOT).amendment[
        "scene_generation_semantics"
    ]
    retention = semantics["end_face_transition"]["point_retention"]
    ribs = semantics["repeated_structure"]

    assert retention == {
        "PRESENT": 1.0,
        "WEAK": 0.10,
        "ABSENT": 0.0,
        "weak_selection_algorithm": (
            "sha256_hash_threshold_over_quantized_point_and_geometry_seed"
        ),
        "weak_selection_is_deterministic": True,
    }
    assert ribs["attach_identical_ribs_to_both_side_walls"] is True
    assert ribs["rib_phase_key_fields"] == (
        "geometry_seed", "scene_id", "scene_variant",
    )
    assert semantics["output_requirements"] == {
        "save_primitive_inventory": True,
        "save_map_checksum": True,
        "save_scan_checksum_before_measurement_noise": True,
        "save_scan_checksum_after_measurement_noise": True,
        "save_normals_checksum": True,
    }
