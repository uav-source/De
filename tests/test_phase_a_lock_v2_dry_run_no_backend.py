import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/dry_run_report.json"


def test_dry_run_executes_no_backend() -> None:
    value = json.loads(REPORT.read_text())
    assert value["FORMAL_BACKEND_EXECUTION_COUNT"] == value["NATIVE_EXECUTION_COUNT"] == 0
    assert value["ATTEMPT_STARTED_COUNT"] == 0

