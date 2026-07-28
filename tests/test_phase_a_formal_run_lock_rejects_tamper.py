import json
from pathlib import Path

import pytest

from zero_perturbation.phase_a_formal_run_lock_v2 import FormalRunLockError, validate_formal_run_lock_payload


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_formal_run_lock_v2.json"


def test_formal_lock_rejects_payload_tamper() -> None:
    value = json.loads(LOCK.read_text())
    value["planned_trial_count"] = 419
    with pytest.raises(FormalRunLockError):
        validate_formal_run_lock_payload(value, root=ROOT)
