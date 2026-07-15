import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from eval import stage2_failure_day10 as day10
from eval.stage2_failure_no_gt_audit import audit_day10_output_files
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]
DAY9_RUN = ROOT / "results/stage2_failure_analysis/day9_quick/stage2_failure_day9_quick_v2"
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
    assert manifest["day9_precondition_pass"] is True
    assert manifest["head_descends_from_day9_checkpoint"] is True
    assert manifest["non_oracle_method_list_pass"] is True
    assert manifest["method_list"] == ["huber_full", "huber_projected_gain"]
    assert manifest["online_continuous_comparison_count"] == 40
    assert manifest["online_discrete_comparison_count"] == 32
    assert manifest["online_record_checksum_mismatch_count"] == 0
    assert manifest["frame_diagnostics_comparison_count"] == 8
    assert manifest["frame_diagnostics_failure_count"] == 0
    assert manifest["frame_diagnostics_checksum_mismatch_count"] == 0
    assert manifest["solver_failure_count_control"] == 0
    assert manifest["solver_failure_count_variant_total"] == 0
    assert manifest["strategy_mismatch_count"] == 0
    assert manifest["failure_frame_record_mismatch_count"] == 0
    assert manifest["window_record_checksum_mismatch_count"] == 0
    assert manifest["gt_field_access_attempt_count"] == 0
    assert manifest["invalid_reset_fixture_row_count"] == 11
    assert manifest["invalid_reset_count"] == 1
    assert manifest["invalid_reset_huber_cusum_match"] is True
    assert manifest["invalid_reset_sign_run_match"] is True
    assert manifest["filesystem_sandbox_pass"] is True
    assert manifest["output_schema_pass"] is True
    assert manifest["detection_threshold_created"] is False
    assert manifest["auroc_computed"] is False
    assert manifest["reserved_test_run_performed"] is False
    assert manifest["STAGE2_GATE"] == "INCOMPLETE"
    assert manifest["STAGE3_GATE"] == "NOT_STARTED"

    json_names = [
        "static_dependency_audit.json",
        "filesystem_sandbox_audit.json",
        "invalid_reset_audit.json",
        "day10_quick_summary.json",
        "run_manifest.json",
    ]
    expected_json_fields = {
        name: list(json.loads((output / name).read_text(encoding="utf-8")))
        for name in json_names
    }
    validation = audit_day10_output_files(
        output,
        manifest["online_equivalence_comparison_count"],
        manifest["window_equivalence_comparison_count"],
        manifest["invalid_reset_fixture_row_count"],
        expected_json_fields,
    )
    assert validation["output_schema_pass"] is True

    missing_csv_field = tmp_path / "missing_csv_field"
    shutil.copytree(output, missing_csv_field)
    csv_path = missing_csv_field / "online_equivalence_audit.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace(",pass", "")
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit_day10_output_files(
        missing_csv_field,
        manifest["online_equivalence_comparison_count"],
        manifest["window_equivalence_comparison_count"],
        manifest["invalid_reset_fixture_row_count"],
        expected_json_fields,
    )["output_schema_pass"] is False

    missing_json_field = tmp_path / "missing_json_field"
    shutil.copytree(output, missing_json_field)
    static_path = missing_json_field / "static_dependency_audit.json"
    static_value = json.loads(static_path.read_text(encoding="utf-8"))
    static_value.pop("audit_pass")
    static_path.write_text(json.dumps(static_value), encoding="utf-8")
    assert audit_day10_output_files(
        missing_json_field,
        manifest["online_equivalence_comparison_count"],
        manifest["window_equivalence_comparison_count"],
        manifest["invalid_reset_fixture_row_count"],
        expected_json_fields,
    )["output_schema_pass"] is False


def _day9_evidence(tmp_path, manifest_updates=None, summary_updates=None):
    manifest = json.loads((DAY9_RUN / "run_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (DAY9_RUN / "day9_quick_summary.json").read_text(encoding="utf-8")
    )
    manifest.update({} if manifest_updates is None else manifest_updates)
    summary.update({} if summary_updates is None else summary_updates)
    manifest_path = tmp_path / "run_manifest.json"
    summary_path = tmp_path / "day9_quick_summary.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return manifest_path, summary_path


def test_day9_precondition_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="manifest is missing"):
        day10.validate_day9_preconditions(
            ROOT,
            tmp_path / "missing.json",
            DAY9_RUN / "day9_quick_summary.json",
        )


def test_day9_precondition_rejects_failed_gate(tmp_path):
    manifest_path, summary_path = _day9_evidence(
        tmp_path,
        manifest_updates={"DAY9_WINDOW_STATS_PASS": False},
    )
    with pytest.raises(RuntimeError, match="DAY9_WINDOW_STATS_PASS"):
        day10.validate_day9_preconditions(ROOT, manifest_path, summary_path)


def test_day9_precondition_rejects_commit_mismatch(tmp_path):
    manifest_path, summary_path = _day9_evidence(
        tmp_path,
        manifest_updates={"git_commit": "0" * 40},
    )
    with pytest.raises(RuntimeError, match="manifest.git_commit"):
        day10.validate_day9_preconditions(ROOT, manifest_path, summary_path)


def test_day9_precondition_rejects_head_without_checkpoint(tmp_path, monkeypatch):
    manifest_path, summary_path = _day9_evidence(tmp_path)
    monkeypatch.setattr(
        day10,
        "_head_descends_from_day9_checkpoint",
        lambda root: False,
    )
    with pytest.raises(RuntimeError, match="HEAD ancestry"):
        day10.validate_day9_preconditions(ROOT, manifest_path, summary_path)


def test_day10_method_list_rejects_oracle_method():
    with pytest.raises(ValueError, match="oracle"):
        day10.validate_day10_method_list(
            ["huber_full", "huber_projected_gain", "huber_oracle_projected_gain"]
        )


def test_day10_dirty_worktree_stops_before_creating_output(tmp_path, monkeypatch):
    monkeypatch.setattr(day10, "git_status_clean", lambda root: False)
    output_root = tmp_path / "outputs"
    with pytest.raises(RuntimeError, match="dirty Git worktree"):
        day10.run_stage2_failure_day10(ROOT, "dirty", output_root)
    assert not output_root.exists()


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
