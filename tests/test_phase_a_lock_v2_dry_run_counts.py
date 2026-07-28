import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/dry_run_report.json"


def test_dry_run_counts_the_frozen_matrix() -> None:
    value = json.loads(REPORT.read_text())
    assert value["PLANNED_SNAPSHOT_COUNT"] == 210
    assert value["PLANNED_TRIAL_COUNT"] == 420
    assert value["PLANNED_OPEN3D_TRIAL_COUNT"] == value["PLANNED_PCL_TRIAL_COUNT"] == 210
    assert value["PLANNED_NATIVE_TRIAL_COUNT"] == 0

