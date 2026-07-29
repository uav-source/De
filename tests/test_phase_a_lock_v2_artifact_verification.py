import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/artifact_verification.json"


def test_final_architecture_artifact_is_independently_verified() -> None:
    value = json.loads(VERIFY.read_text())
    assert value["LOCK_ARCHITECTURE_V2_ARTIFACT_VERIFICATION_PASS"] is False
    assert value["missing_files"] == []
    assert value["sha256_mismatches"] == []
    assert value["sha256_missing_files"] == []
    assert value["semantic_failures"] == ["PHASE_A_LOCK_ARCHITECTURE_V2_PASS"]
