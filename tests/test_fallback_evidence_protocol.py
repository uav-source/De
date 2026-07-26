import json
from pathlib import Path

from eval.day5_v5_adjudication import (
    FALLBACK_PROTOCOL,
    fallback_protocol_summary,
)


ROOT = Path(__file__).resolve().parents[1]


def test_fallback_protocol_is_frozen_but_not_executed():
    assert FALLBACK_PROTOCOL["fallback_protocol_frozen"] is True
    assert FALLBACK_PROTOCOL["fallback_execution_authorized"] is False
    assert (
        FALLBACK_PROTOCOL["day5_fallback_in_call_immutability_authorized"]
        == "PENDING_GPT_REVIEW"
    )
    assert FALLBACK_PROTOCOL["day6_quick_diagnostics_authorized"] is False


def test_fallback_protocol_has_four_preregistered_parts():
    parts = {part["id"]: part for part in FALLBACK_PROTOCOL["parts"]}
    assert set(parts) == {"A", "B", "C", "D"}
    assert parts["A"]["target_gate"] == "TAP_IN_CALL_IMMUTABILITY_PASS"
    assert (
        parts["B"]["target_gate"]
        == "FROZEN_REAL_OBSERVATION_RECORD_PASS"
    )
    assert parts["B"]["holdout_or_future_test_allowed"] is False
    assert parts["C"]["minimum_repeat_count"] == 3
    assert parts["D"]["forbidden_claim"] == "BITWISE_REPLAY_EQUIVALENCE"


def test_fallback_manifest_matches_code_and_hash():
    path = (
        ROOT
        / "manifests/harmful_bias/"
        "fallback_readonly_evidence_protocol_v1.json"
    )
    assert json.loads(path.read_text(encoding="utf-8")) == FALLBACK_PROTOCOL
    assert fallback_protocol_summary()["fallback_protocol_sha256"] == (
        "9ab4bcd7de04bd9a04858484b07897ec205e3619d4c43521aeacc5378f215616"
    )


def test_fixed_scientific_and_authorization_state():
    manifest = json.loads(
        (
            ROOT
            / "manifests/harmful_bias/day5_v5_adjudication_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["STAGE2_GATE"] == "FAIL"
    assert manifest["TRANSITION"] == "PIVOT"
    assert manifest["DAY5_STARTUP_SYNC_V5_PASS"] is False
    assert manifest["DAY5_RUNTIME_EQUIVALENCE_PASS"] is False
    assert manifest["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert manifest["STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED"] is False
    assert manifest["FALLBACK_EXECUTION_AUTHORIZED"] is False
    assert manifest["FAST_LIO2_INTEGRATION_AUTHORIZED"] is False
    assert manifest["HARMFUL_BIAS_DETECTABILITY_STATUS"] == (
        "NOT_EVALUATED_DAY5_V5_ADJUDICATION"
    )
