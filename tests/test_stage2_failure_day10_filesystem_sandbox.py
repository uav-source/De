from pathlib import Path

from eval.stage2_failure_no_gt_audit import run_filesystem_sandbox_audit


ROOT = Path(__file__).resolve().parents[1]
DAY8_RUN = ROOT / "results/stage2_failure_analysis/day8_quick/stage2_failure_day8_quick_v2"


def test_day9_filesystem_sandbox_needs_no_gt_and_ignores_fake_gt(tmp_path):
    audit = run_filesystem_sandbox_audit(
        ROOT,
        tmp_path / "sandboxes",
        DAY8_RUN / "frame_diagnostics_online.csv",
        DAY8_RUN / "run_manifest.json",
    )
    assert audit["no_gt_subprocess_return_code"] == 0
    assert audit["fake_gt_subprocess_return_code"] == 0
    assert audit["output_byte_identical"] is True
    assert audit["gt_file_required"] is False
    assert audit["fake_gt_file_affected_output"] is False
    assert audit["sandbox_pass"] is True
