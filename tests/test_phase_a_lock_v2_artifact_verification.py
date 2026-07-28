import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/artifact_verification.json"


def test_final_architecture_artifact_is_independently_verified() -> None:
    assert json.loads(VERIFY.read_text())["LOCK_ARCHITECTURE_V2_ARTIFACT_VERIFICATION_PASS"] is True
