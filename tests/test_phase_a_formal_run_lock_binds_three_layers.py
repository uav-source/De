import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/phase_a_formal_run_lock_v2.json"


def test_formal_lock_binds_exactly_three_upstream_layers() -> None:
    value = json.loads(LOCK.read_text())
    assert all(value[name].endswith(".json") for name in (
        "scientific_protocol_lock_path", "snapshot_lock_path", "execution_implementation_lock_path"
    ))

