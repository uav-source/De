from backend_phase_a_test_support import protocol


def test_native_is_excluded_from_every_phase_a_plan_row():
    phase = protocol()
    assert phase.self_audit()["NATIVE_PLANNED_TRIAL_COUNT"] == 0
    assert not any("native" in row.backend.lower() for row in phase.planned_trials())
    assert phase.data["formal_backends"]["excluded"]["native_full"]["reason"] == (
        "native_full_failed_ideal_matched_control"
    )
