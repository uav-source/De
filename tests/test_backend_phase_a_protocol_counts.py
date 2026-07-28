from backend_phase_a_test_support import protocol


def test_phase_a_protocol_has_exact_frozen_cardinalities():
    audit = protocol().self_audit()
    assert audit["PROTOCOL_HAS_EXACTLY_7_SCENES"] is True
    assert audit["PROTOCOL_HAS_EXACTLY_3_GEOMETRY_SEEDS"] is True
    assert audit["PROTOCOL_HAS_EXACTLY_2_MEASUREMENT_SEEDS"] is True
    assert audit["PROTOCOL_HAS_EXACTLY_5_REPEATS"] is True
    assert audit["PLANNED_SNAPSHOT_COUNT"] == 210
    assert audit["PLANNED_TRIAL_COUNT"] == 420
