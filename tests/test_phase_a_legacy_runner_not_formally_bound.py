import subprocess
import sys
from pathlib import Path

from phase_a_v2_active_runner_support import (
    LEGACY_RUNNER_RELATIVE,
    file_sha256,
    resolve_active_formal_runner,
)


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_runner_is_not_bound_by_formal_run_lock_v2() -> None:
    binding = resolve_active_formal_runner(ROOT)
    legacy = ROOT / LEGACY_RUNNER_RELATIVE
    assert legacy.is_file()
    assert binding.active_runner.resolve() != legacy.resolve()
    assert binding.active_runner_sha256 != file_sha256(legacy)


def test_legacy_runner_rejecting_v2_interface_is_expected_isolation() -> None:
    legacy = ROOT / LEGACY_RUNNER_RELATIVE
    help_result = subprocess.run(
        [sys.executable, str(legacy), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--protocol-lock" in help_result.stdout
    assert "--snapshot-lock" in help_result.stdout
    assert "--formal-run-lock" not in help_result.stdout
