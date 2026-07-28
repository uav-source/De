from backend_phase_a_test_support import artifact_json, protocol


CONFIRMATORY_VALUES = {
    248284635,
    376488233,
    198112089,
    229684695,
    226655024,
    469989467,
    1088311622,
    916609326,
}


def test_confirmatory_and_old_capture_rng_instantiation_counts_remain_zero():
    phase = protocol()
    planned_values = set(phase.geometry_seeds) | set(phase.measurement_seeds)
    assert planned_values.isdisjoint(CONFIRMATORY_VALUES)
    audit = artifact_json("seed_usage_audit.json")
    assert audit["CONFIRMATORY_RNG_INSTANTIATION_COUNT"] == 0
    assert audit["OLD_CAPTURE_TEST_RNG_INSTANTIATION_COUNT"] == 0
    assert audit["NATIVE_FORMAL_EXECUTION_COUNT"] == 0
