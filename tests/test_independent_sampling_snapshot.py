from zero_perturbation_test_support import development_snapshot


def test_independent_sampling_has_distinct_scene_realization_from_ideal_subset():
    ideal = development_snapshot("IDEAL_MATCHED")
    independent = development_snapshot("INDEPENDENT_NOISE_FREE")
    assert ideal.checksums["scene_checksum"] != independent.checksums["scene_checksum"]
    assert ideal.checksums["scan_checksum"] != independent.checksums["scan_checksum"]
