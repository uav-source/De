from eval.stage2_day14_decision import _build_gate_summary
from eval.stage2_day14_schema import (
    GateResult,
    GateStatus,
    make_stage2_decision,
)


def _gate(name, status):
    return GateResult(name, status, "threshold", "observed", "reason", ())


def test_stage2_failure_authorizes_only_detector_pivot():
    decision = make_stage2_decision(
        _gate("separability", GateStatus.FAIL),
        _gate("cross_geometry", GateStatus.PASS),
        _gate("causal_consistency", GateStatus.FAIL),
        _gate("no_gt", GateStatus.PASS),
        True,
    )
    summary = _build_gate_summary(decision, "PARTIAL_OR_FAIL")
    assert summary["STAGE2_GATE"] == "FAIL"
    assert summary["PATENT2_AUTHORIZED"] is False
    assert summary["COMPLETE_DEGEN_LIO_TRO_ROUTE_AUTHORIZED"] is False
    assert summary["DETECTOR_PAPER_PIVOT_AUTHORIZED"] is True
    assert summary["DETECTOR_ONLY_REAL_LIO_ADAPTER_PRIVATE_WORK"] == "AUTHORIZED"
    assert summary["FULL_DEGEN_LIO_FASTLIO2_INTEGRATION"] == "NOT_AUTHORIZED"

