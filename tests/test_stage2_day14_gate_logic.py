from eval.stage2_day14_schema import (
    GateResult,
    GateStatus,
    make_stage2_decision,
)


def _gate(name, status):
    return GateResult(name, status, "threshold", "observed", "reason", ())


def test_one_failed_gate_defeats_three_passes_without_majority_vote():
    decision = make_stage2_decision(
        _gate("separability", GateStatus.FAIL),
        _gate("cross_geometry", GateStatus.PASS),
        _gate("causal_consistency", GateStatus.PASS),
        _gate("no_gt", GateStatus.PASS),
        True,
    )
    assert decision.overall_gate == GateStatus.FAIL
    assert decision.coherent_bias_harmful_mechanism_supported is True
    assert decision.coherent_bias_stably_online_detectable is False
    assert decision.stage3_start_authorized is False
    assert decision.transition == "PIVOT"


def test_not_established_is_never_treated_as_pass():
    decision = make_stage2_decision(
        _gate("separability", GateStatus.PASS),
        _gate("cross_geometry", GateStatus.NOT_ESTABLISHED),
        _gate("causal_consistency", GateStatus.PASS),
        _gate("no_gt", GateStatus.PASS),
        None,
    )
    assert decision.overall_gate == GateStatus.FAIL

