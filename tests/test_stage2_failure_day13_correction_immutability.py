import subprocess
from pathlib import Path

import pytest

from eval.stage2_failure_day13_correction_v2 import _validate_output_location


ROOT = Path(__file__).resolve().parents[1]
LOCKED_V1_FILES = (
    "src/eval/stage2_failure_day13_seeds.py",
    "src/eval/stage2_failure_day13_design.py",
    "src/eval/stage2_failure_day13_statistics.py",
    "src/eval/stage2_failure_day13_causal.py",
    "src/eval/stage2_failure_day13_schema.py",
    "src/eval/stage2_failure_day13.py",
    "scripts/38_run_stage2_failure_day13.py",
)


def test_v1_locked_analysis_files_have_no_correction_diff():
    result = subprocess.run(
        [
            "git", "diff", "checkpoint/day13-v1-before-analysis-correction", "--",
            *LOCKED_V1_FILES,
        ],
        cwd=str(ROOT), check=True, text=True, stdout=subprocess.PIPE,
    )
    assert result.stdout == ""


def test_output_cannot_equal_or_descend_from_source(tmp_path):
    source = tmp_path / "v1"
    with pytest.raises(ValueError):
        _validate_output_location(source, source)
    with pytest.raises(ValueError):
        _validate_output_location(source, source / "v2")


def test_correction_script_exposes_only_offline_arguments():
    source = (ROOT / "scripts/39_run_stage2_failure_day13_correction.py").read_text()
    for allowed in ("--source-run-dir", "--output-dir", "--overwrite"):
        assert allowed in source
    for forbidden in (
        "--calibration", "--evaluation", "--resume", "--test",
        "--reserved-test", "--retune", "--select-best",
    ):
        assert forbidden not in source

