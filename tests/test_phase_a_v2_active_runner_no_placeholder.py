import json
import subprocess
import sys
from pathlib import Path

from phase_a_v2_active_runner_support import resolve_active_formal_runner


ROOT = Path(__file__).resolve().parents[1]


def test_active_runner_exposes_only_formal_lock_interface() -> None:
    runner = resolve_active_formal_runner(ROOT).active_runner
    result = subprocess.run(
        [sys.executable, str(runner), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--formal-run-lock" in result.stdout
    assert "--protocol-lock" not in result.stdout
    assert "--snapshot-lock" not in result.stdout


def test_active_runner_dry_run_reaches_complete_nonexecuting_plan(tmp_path: Path) -> None:
    binding = resolve_active_formal_runner(ROOT)
    output = tmp_path / "formal-output-must-not-be-created"
    result = subprocess.run(
        [
            sys.executable,
            str(binding.active_runner),
            "--formal-run-lock",
            str(binding.formal_lock),
            "--run-id",
            "regression-repair-active-runner-dry-run",
            "--output-dir",
            str(output),
            "--workers",
            "4",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["FORMAL_DRY_RUN_PASS"] is True
    assert report["PLANNED_SNAPSHOT_COUNT"] == 210
    assert report["PLANNED_TRIAL_COUNT"] == 420
    assert report["PLANNED_OPEN3D_TRIAL_COUNT"] == 210
    assert report["PLANNED_PCL_TRIAL_COUNT"] == 210
    assert report["PLANNED_NATIVE_TRIAL_COUNT"] == 0
    assert report["FORMAL_SEED_ACCESS_COUNT"] == 0
    assert report["FORMAL_BACKEND_EXECUTION_COUNT"] == 0
    assert report["FORMAL_TRIAL_RESULT_COUNT"] == 0
    assert not output.exists()
