from eval.stage2_failure_day11b_schema import build_pairing_audit


def _manifest(stress, method):
    return {
        "sweep": "geometry", "level": "L4", "stress": stress,
        "geometry_seed": 4003, "sensor_seed": 111, "process_seed": 6015,
        "method": method, "scene_checksum": "scene", "base_observation_checksum": "base",
        "stressed_observation_checksum": stress, "stress_checksum": stress,
        "process_noise_checksum": "process", "initial_state_checksum": "state",
        "initial_covariance_checksum": "covariance",
        "contaminated_measurement_count": 0 if stress == "clean" else 10,
        "stress_active_frame_count": 0 if stress == "clean" else 5,
    }


def _rows():
    return [_manifest(stress, method) for stress in ("clean", "coherent_subhuber_slip") for method in ("huber_full", "huber_projected_gain")]


def test_method_and_stress_pairing_checksums_pass():
    audit = build_pairing_audit(_rows())
    assert len(audit) == 3
    assert all(row["pairing_valid"] for row in audit)


def test_method_checksum_mismatch_is_rejected():
    rows = _rows()
    rows[1]["process_noise_checksum"] = "different"
    assert any(not row["pairing_valid"] for row in build_pairing_audit(rows))


def test_clean_contamination_and_empty_coherent_are_rejected():
    rows = _rows()
    rows[0]["contaminated_measurement_count"] = 1
    assert any(not row["pairing_valid"] for row in build_pairing_audit(rows))
    rows = _rows()
    for row in rows:
        if row["stress"] == "coherent_subhuber_slip":
            row["contaminated_measurement_count"] = 0
            row["stress_active_frame_count"] = 0
    assert any(not row["pairing_valid"] for row in build_pairing_audit(rows))
