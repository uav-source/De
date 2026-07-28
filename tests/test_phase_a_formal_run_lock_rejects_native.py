import json
from pathlib import Path

import pytest

from zero_perturbation.phase_a_formal_run_lock_v2 import FormalRunLockError, validate_formal_run_lock_payload
from zero_perturbation.phase_a_trial_result_schema import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_formal_run_lock_v2.json"


def test_formal_lock_rejects_native_backend() -> None:
    value = json.loads(LOCK.read_text())
    value["allowed_backends"].append("native_full")
    value.pop("formal_payload_sha256")
    value["formal_payload_sha256"] = canonical_json_sha256(value)
    with pytest.raises(FormalRunLockError):
        validate_formal_run_lock_payload(value, root=ROOT)

