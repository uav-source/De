import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval import stage2_failure_day10 as day10
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OUTPUTS = {
    "online_equivalence_audit.csv",
    "window_equivalence_audit.csv",
    "static_dependency_audit.json",
    "filesystem_sandbox_audit.json",
    "invalid_reset_end_to_end.csv",
    "invalid_reset_audit.json",
    "day10_quick_summary.json",
    "run_manifest.json",
}


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("use_reserved_test", True),
        ("formal_experiment", True),
        ("replay_stage2c_representative_seed", True),
        ("create_detection_threshold", True),
        ("compute_auroc", True),
        ("compute_fpr", True),
        ("compute_f1", True),
        ("compute_detection_delay", True),
        ("frame_limit", 7),
        ("continuous_comparison_tolerance", 1.0e-9),
    ],
)
def test_day10_quick_config_strictly_freezes_scientific_switches(name, value):
    config = load_yaml(ROOT / "configs/stage2_failure/day10_quick.yaml")
    config[name] = value
    with pytest.raises(ValueError, match="freezes"):
        day10.validate_day10_quick_config(config)


def test_day10_quick_writes_complete_passing_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(day10, "git_status_clean", lambda root: True)
    manifest = day10.run_stage2_failure_day10(
        ROOT,
        "pytest_day10_quick",
        tmp_path / "day10",
    )
    output = tmp_path / "day10/pytest_day10_quick"
    assert {path.name for path in output.iterdir()} == EXPECTED_OUTPUTS
    written = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert written == manifest
    assert manifest["DAY10_NO_GT_AUDIT_PASS"] is True
    assert manifest["method_list"] == ["huber_full", "huber_projected_gain"]
    assert manifest["online_continuous_comparison_count"] == 40
    assert manifest["online_discrete_comparison_count"] == 32
    assert manifest["online_record_checksum_mismatch_count"] == 0
    assert manifest["window_record_checksum_mismatch_count"] == 0
    assert manifest["gt_field_access_attempt_count"] == 0
    assert manifest["invalid_reset_fixture_row_count"] == 11
    assert manifest["invalid_reset_count"] == 1
    assert manifest["filesystem_sandbox_pass"] is True
    assert manifest["detection_threshold_created"] is False
    assert manifest["auroc_computed"] is False
    assert manifest["reserved_test_run_performed"] is False
    assert manifest["STAGE2_GATE"] == "INCOMPLETE"
    assert manifest["STAGE3_GATE"] == "NOT_STARTED"


def test_day10_cli_rejects_unsupported_modes():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/34_run_stage2_failure_day10.py"),
            "--quick",
            "--run-id",
            "rejected",
            "--test",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 2
    assert "unrecognized arguments: --test" in completed.stderr
