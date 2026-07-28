import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/179_run_backend_phase_a_v2.py"


def test_runner_exposes_only_the_frozen_lock_interface() -> None:
    result = subprocess.run([str(RUNNER), "--help"], check=True, capture_output=True, text=True)
    for allowed in ("--formal-run-lock", "--run-id", "--output-dir", "--workers", "--resume", "--dry-run"):
        assert allowed in result.stdout
    for forbidden in ("--ignore-lock", "--override", "--legacy-lock", "--protocol-lock", "--snapshot-lock", "--native"):
        assert forbidden not in result.stdout

