import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval import stage2_failure_day11a as day11a


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OUTPUTS = {
    "candidate_pool.csv",
    "deterministic_diagnostic_case_lock.json",
    "protocol_revision_manifest.json",
    "day11a_forbidden_dependency_audit.json",
    "day11a_summary.json",
    "run_manifest.json",
}


def run_pipeline(tmp_path, monkeypatch, run_id):
    monkeypatch.setattr(day11a, "git_status_clean", lambda root: True)
    return day11a.run_stage2_failure_day11a(ROOT, run_id, tmp_path)


def test_day11a_pipeline_writes_complete_passing_case_lock(tmp_path, monkeypatch):
    manifest = run_pipeline(tmp_path, monkeypatch, "pipeline")
    output = tmp_path / "pipeline"
    assert {path.name for path in output.iterdir()} == EXPECTED_OUTPUTS
    assert manifest["DAY11A_CASE_LOCK_PASS"] is True
    assert manifest["DAY11B_DETERMINISTIC_REPLAY_AUTHORIZED"] is True
    assert manifest["STAGE2C_HISTORY_RECOVERY_PASS"] is False
    assert manifest["DAY11_REPLAY_PASS"] is False
    assert manifest["geometry_candidate_count"] == 800
    assert manifest["observation_candidate_count"] == 800
    assert manifest["candidate_duplicate_count"] == 0
    assert manifest["geometry_selected_row_count"] == 1
    assert manifest["observation_selected_row_count"] == 1
    assert manifest["forbidden_dependency_audit_pass"] is True
    assert manifest["historical_artifacts_unchanged"] is True
    assert manifest["day11b_replay_stress_regimes"] == [
        "clean",
        "coherent_subhuber_slip",
    ]
    assert manifest["stage2c_allowed_stress_regimes"] == [
        "clean",
        "coherent_subhuber_slip",
        "gross_outlier_control",
    ]
    written = json.loads((output / "run_manifest.json").read_text())
    assert written == manifest


def test_repeated_pipeline_has_byte_identical_pool_and_scientific_lock(
    tmp_path, monkeypatch
):
    run_pipeline(tmp_path, monkeypatch, "first")
    run_pipeline(tmp_path, monkeypatch, "second")
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert (first / "candidate_pool.csv").read_bytes() == (
        second / "candidate_pool.csv"
    ).read_bytes()
    first_lock = json.loads(
        (first / "deterministic_diagnostic_case_lock.json").read_text()
    )
    second_lock = json.loads(
        (second / "deterministic_diagnostic_case_lock.json").read_text()
    )
    assert day11a.scientific_lock_content(first_lock) == day11a.scientific_lock_content(
        second_lock
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selection_uses_metrics", True),
        ("selection_uses_innovation", True),
        ("selection_uses_cusum", True),
        ("selection_uses_gt_error", True),
        ("selection_uses_manual_override", True),
        ("run_replay", True),
        ("generate_figures", True),
        ("compute_auroc", True),
        ("expected_day11b_method_replay_count", 10),
    ],
)
def test_day11a_config_strictly_freezes_scientific_fields(field, value):
    config = day11a.load_yaml(
        ROOT / "configs/stage2_failure/day11a_case_lock.yaml"
    )
    config[field] = value
    with pytest.raises(ValueError, match="freezes|eight"):
        day11a.validate_day11a_config(config)


@pytest.mark.parametrize(
    "unsupported",
    ["--replay", "--manual-seed", "--override", "--ignore-lock", "--test", "--plot", "--auroc", "--geometry-seed"],
)
def test_day11a_cli_rejects_unsupported_modes_and_seed_arguments(unsupported):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/35_run_stage2_failure_day11a.py"),
            "--lock-cases",
            "--run-id",
            "rejected",
            unsupported,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode != 0
    assert "unrecognized arguments" in completed.stderr


def test_dirty_worktree_stops_before_output_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(day11a, "git_status_clean", lambda root: False)
    with pytest.raises(RuntimeError, match="dirty Git worktree"):
        day11a.run_stage2_failure_day11a(ROOT, "dirty", tmp_path)
    assert not (tmp_path / "dirty").exists()
