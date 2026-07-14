from eval.weak_update_stage2c import METHODS, audit_method_pairing


def _rows():
    return [{
        "sweep": "geometry", "level": "L3", "stress": "clean",
        "geometry_seed": 2801, "sensor_seed": 77, "process_seed": 4001,
        "method": method, "observation_checksum": "o", "stress_checksum": "s",
        "process_noise_checksum": "p", "initial_state_checksum": "i",
        "initial_covariance_checksum": "c",
    } for method in METHODS]


def test_pairing_requires_all_five_methods_and_identical_random_inputs():
    rows = _rows()
    assert audit_method_pairing(rows)[0]["pairing_valid"] is True
    rows[-1]["process_noise_checksum"] = "different"
    assert audit_method_pairing(rows)[0]["pairing_valid"] is False
