import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_2"


def test_execution_chain_v1_2_tampered_result_is_rejected_without_overwrite():
    value = json.loads((ARTIFACT / "tamper_audit.json").read_text())
    assert value["TAMPERED_RESULT_REJECTED"] is True
    assert value["RESUME_DID_NOT_OVERWRITE_TAMPERED_RESULT"] is True
