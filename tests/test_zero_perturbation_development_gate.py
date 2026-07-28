from zero_perturbation.development_analysis import (
    CONFIRMATORY_LOCK_PREREQUISITES,
    confirmatory_lock_authorized,
)


def test_confirmatory_lock_gate_is_exact_conjunction_and_never_run_authority():
    decisions = {name: True for name in CONFIRMATORY_LOCK_PREREQUISITES}
    decisions["NEW_PROTOCOL_AMBIGUITIES_FOUND"] = False
    assert confirmatory_lock_authorized(decisions)
    decisions["IDEAL_MATCHED_CONTROL_PASS"] = False
    assert not confirmatory_lock_authorized(decisions)
