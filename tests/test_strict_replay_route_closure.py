from pathlib import Path

from eval.day5_v5_adjudication import (
    full_matrix_status,
    route_closure_summary,
)


ROOT = Path(__file__).resolve().parents[1]


def test_strict_route_is_closed_without_proof():
    result = route_closure_summary()
    assert (
        result["STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS"]
        == "ABANDONED_AFTER_V5"
    )
    assert result["STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED"] is False
    assert result["CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE"] == "NOT_PROVEN"
    assert result["STRICT_ROUTE_CLOSURE_PASS"] is True


def test_route_closure_does_not_authorize_v6_or_alias():
    result = route_closure_summary()
    assert result["v6_created"] is False
    assert result["same_route_under_other_name_authorized"] is False
    assert all("V6_AUTHORIZED" not in key for key in result)


def test_full_matrix_remains_not_evaluated():
    result = full_matrix_status()
    assert result["CORRECTED_FULL_MATRIX_RESULT"] == (
        "NOT_EVALUATED_INCOMPLETE_MATRIX"
    )
    assert result["DAY5_STARTUP_SYNC_V5_PASS"] is False


def test_route_closure_document_preserves_claim_boundary():
    text = (
        ROOT / "docs/harmful_bias/strict_replay_route_closure.md"
    ).read_text(encoding="utf-8")
    assert "ABANDONED_AFTER_V5" in text
    assert "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN" in text
    assert "Formal Degen-LIO remains incomplete" in text
