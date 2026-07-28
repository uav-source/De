import json
from pathlib import Path

import pytest

from zero_perturbation.phase_a_implementation_lock_v2 import ImplementationLockError, validate_implementation_lock
from zero_perturbation.phase_a_trial_result_schema import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_execution_implementation_lock_v2.json"


def test_implementation_lock_rejects_seed() -> None:
    value = json.loads(LOCK.read_text())
    value["geometry_seed"] = 1
    value.pop("implementation_payload_sha256")
    value["implementation_payload_sha256"] = canonical_json_sha256(value)
    with pytest.raises(ImplementationLockError):
        validate_implementation_lock(value, root=ROOT, verify_current_files=False)

