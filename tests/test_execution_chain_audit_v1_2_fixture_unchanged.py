import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_2"


def test_execution_chain_v1_2_fixture_contract_is_unchanged():
    value = json.loads((ARTIFACT / "fixture_contract_diff.json").read_text())
    assert value["fixture_checksum_difference_count"] == 0
    assert value["fixture_reference_pose_difference_count"] == 0
    assert value["fixture_expected_outcome_difference_count"] == 0
