import json
from pathlib import Path

from zero_perturbation.phase_a_formal_run_lock_v2 import formal_run_lock_duplicated_contract_fields


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_formal_run_lock_v2.json"


def test_formal_lock_has_no_duplicated_contract_payload() -> None:
    assert formal_run_lock_duplicated_contract_fields(json.loads(LOCK.read_text())) == []

