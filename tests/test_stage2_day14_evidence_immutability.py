import subprocess
from pathlib import Path

from eval.analysis_lock import compute_directory_hash, sha256_file
from eval import stage2_day14_decision as day14


ROOT = Path(__file__).resolve().parents[1]
DAY13_V2 = ROOT / "artifacts/current/stage2_day13_analysis_correction_v2"


def _hashes():
    v1 = ROOT / (
        "results/stage2_failure_analysis/day13_new_seed/"
        "stage2_failure_day13_new_seed_v1"
    )
    return {
        "v1_design": sha256_file(v1 / "design/design_lock.json"),
        "v1_summary": sha256_file(v1 / "day13_summary.json"),
        "v2": compute_directory_hash(DAY13_V2),
        "stage2b": compute_directory_hash(
            ROOT / "artifacts/history/stage2b_column_scaling_no_go"
        ),
        "stage2c": compute_directory_hash(ROOT / "artifacts/current/weak_update_stage2c"),
    }


def test_day14_pipeline_does_not_mutate_frozen_evidence(tmp_path, monkeypatch):
    before = _hashes()
    monkeypatch.setattr(day14, "_git_worktree_clean", lambda root: True)
    day14.finalize_stage2_day14(
        ROOT,
        ROOT / "configs/stage2/day14_decision.yaml",
        DAY13_V2,
        tmp_path / "artifact",
        report_path=tmp_path / "report.md",
    )
    assert _hashes() == before


def test_day14_has_no_stage3_diff():
    result = subprocess.run(
        [
            "git", "diff", "checkpoint/day13-v2-pass-before-day14", "--",
            "src/stage3", "configs/stage3",
        ],
        cwd=str(ROOT), check=True, stdout=subprocess.PIPE, text=True,
    )
    assert result.stdout == ""

