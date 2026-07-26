from fastlio2_adapter.day6_fallback_functional_diagnostics import (
    REQUIRED_GATE_NAMES,
    evaluate_day6_gate,
)


def test_all_required_functional_gates_pass_without_phase_authorization():
    result = evaluate_day6_gate({name: True for name in REQUIRED_GATE_NAMES})
    assert result["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS"] is True
    assert result["NEXT_PHASE_RECOMMENDED"] is True
    assert result["NEXT_PHASE_AUTHORIZED"] is False
    assert result["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert result["CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE"] == "NOT_PROVEN"
    assert result["STAGE2_GATE"] == "FAIL"
    assert result["TRANSITION"] == "PIVOT"


def test_one_missing_required_gate_fails_all_final_day6_passes():
    facts = {name: True for name in REQUIRED_GATE_NAMES}
    facts["PLOTS_COMPLETE"] = False
    result = evaluate_day6_gate(facts)
    assert result["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS"] is False
    assert result["NEXT_PHASE_RECOMMENDED"] is False


def test_exact_cross_run_equality_cannot_restore_strict_gate():
    result = evaluate_day6_gate({name: True for name in REQUIRED_GATE_NAMES})
    assert result["CROSS_RUN_EXACT_OUTPUT_EQUALITY_REQUIRED"] is False
    assert result["CROSS_RUN_BITWISE_EQUIVALENCE_CLAIMED"] is False
    assert result["FAST_LIO2_INTEGRATION_AUTHORIZED"] is False
