import json
from pathlib import Path

from zero_perturbation.phase_a_implementation_lock_v2 import implementation_lock_scientific_fields


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_execution_implementation_lock_v2.json"


def test_implementation_lock_contains_no_scientific_fields() -> None:
    assert implementation_lock_scientific_fields(json.loads(LOCK.read_text())) == []

