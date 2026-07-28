import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/dry_run_report.json"


def test_dry_run_writes_no_trial_results() -> None:
    assert json.loads(REPORT.read_text())["FORMAL_TRIAL_RESULT_COUNT"] == 0

