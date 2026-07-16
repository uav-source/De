from eval.stage2_failure_day13 import _pairing_audit


def _summary(stress):
    row = {"role": "evaluation", "sweep": "geometry", "level": "L3", "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3, "stress": stress}
    for field in ("scene_checksum", "points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum", "plane_points_world_base_checksum", "process_noise_checksum", "initial_state_checksum", "initial_covariance_checksum"):
        row[field] = "same"
    return row


def test_clean_coherent_gross_share_all_base_inputs():
    rows = _pairing_audit([_summary(name) for name in ("clean", "coherent_subhuber_slip", "gross_outlier_control")])
    assert len(rows) == 1
    assert rows[0]["pairing_valid"] is True
