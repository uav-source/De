import json
from pathlib import Path

import pytest

from zero_perturbation.phase_a_implementation_lock_v2 import ImplementationLockError, validate_implementation_lock
from zero_perturbation.phase_a_trial_result_schema import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_execution_implementation_lock_v2.json"


def test_implementation_lock_requires_publisher() -> None:
    value = json.loads(LOCK.read_text())
    value["implementation_bindings"].pop("publisher_sha256")
    value.pop("implementation_payload_sha256")
    value["implementation_payload_sha256"] = canonical_json_sha256(value)
    with pytest.raises(ImplementationLockError):
        validate_implementation_lock(value, root=ROOT, verify_current_files=False)

