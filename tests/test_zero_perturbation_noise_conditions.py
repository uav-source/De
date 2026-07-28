from zero_perturbation_test_support import development_protocol


def test_six_noise_conditions_are_exact_and_frozen():
    protocol = development_protocol()
    assert protocol.conditions == (
        "IDEAL_MATCHED",
        "INDEPENDENT_NOISE_FREE",
        "SCAN_NOISE_ONLY",
        "MAP_NOISE_ONLY",
        "DROPOUT_ONLY",
        "FULL_NOISE",
    )
    full = protocol.condition("FULL_NOISE")
    assert full["scan_noise_sigma_m"] == 0.003
    assert full["map_noise_sigma_m"] == 0.001
    assert full["scan_dropout_fraction"] == 0.01
