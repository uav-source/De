import copy

from eval.stage2_failure_day11b_provenance import build_base_observation_pairing_audit


CHECKSUM_FIELDS = (
    "points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum",
    "plane_points_world_base_checksum", "plane_points_world_stressed_checksum",
    "initial_state_checksum", "initial_covariance_checksum", "process_noise_checksum",
    "scene_checksum", "stress_checksum",
)


def _manifests():
    rows = []
    for stress in ("clean", "coherent_subhuber_slip"):
        for method in ("huber_full", "huber_projected_gain"):
            row = {
                "sweep": "geometry", "level": "L4", "stress": stress,
                "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3,
                "method": method,
            }
            row.update({field: f"shared-{field}" for field in CHECKSUM_FIELDS})
            row["stress_checksum"] = f"stress-{stress}"
            row["plane_points_world_stressed_checksum"] = f"plane-{stress}"
            rows.append(row)
    return rows


def _counts(rows):
    return build_base_observation_pairing_audit(rows)[1]


def test_all_frozen_base_observation_pairs_pass():
    assert all(value == 0 for value in _counts(_manifests()).values())


def test_each_method_pair_base_checksum_mismatch_is_detected():
    for field, counter in (
        ("points_lidar_base_checksum", "points_lidar_method_pair_mismatch_count"),
        ("normals_world_base_checksum", "normals_world_method_pair_mismatch_count"),
        ("R_diag_list_checksum", "R_diag_method_pair_mismatch_count"),
    ):
        rows = copy.deepcopy(_manifests())
        rows[1][field] = "changed"
        assert _counts(rows)[counter] == 1


def test_each_clean_stress_base_checksum_mismatch_is_detected():
    for field, counter in (
        ("points_lidar_base_checksum", "points_lidar_clean_stress_mismatch_count"),
        ("normals_world_base_checksum", "normals_world_clean_stress_mismatch_count"),
        ("R_diag_list_checksum", "R_diag_clean_stress_mismatch_count"),
    ):
        rows = copy.deepcopy(_manifests())
        for row in rows:
            if row["stress"] == "coherent_subhuber_slip":
                row[field] = "changed-together"
        assert _counts(rows)[counter] == 2
