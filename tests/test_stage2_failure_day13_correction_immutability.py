import ast
import subprocess
from pathlib import Path

import pytest

from eval.stage2_failure_day13_correction_v2 import _validate_output_location


ROOT = Path(__file__).resolve().parents[1]
LOCKED_V1_FILES = (
    "src/eval/stage2_failure_day13_design.py",
    "src/eval/stage2_failure_day13_statistics.py",
    "src/eval/stage2_failure_day13_causal.py",
    "src/eval/stage2_failure_day13_schema.py",
    "src/eval/stage2_failure_day13.py",
    "scripts/38_run_stage2_failure_day13.py",
)
SEED_MODULE = "src/eval/stage2_failure_day13_seeds.py"
LOCKED_SEED_GENERATION_SYMBOLS = frozenset({
    "SEED_NAMESPACE",
    "SEED_MIN",
    "SEED_MODULUS",
    "SEED_TYPES",
    "SEED_ROLES",
    "SEED_COUNTS",
    "seed_label",
    "seed_candidate",
    "generate_seed",
    "generate_seed_namespace",
})


def test_v1_locked_analysis_files_have_no_correction_diff():
    result = subprocess.run(
        [
            "git", "diff", "checkpoint/day13-v1-before-analysis-correction", "--",
            *LOCKED_V1_FILES,
        ],
        cwd=str(ROOT), check=True, text=True, stdout=subprocess.PIPE,
    )
    assert result.stdout == ""


def _locked_seed_generation_ast(source: str) -> dict[str, str]:
    result = {}
    for node in ast.parse(source).body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                name = targets[0].id
        if name in LOCKED_SEED_GENERATION_SYMBOLS:
            result[name] = ast.dump(node, include_attributes=False)
    return result


def test_v1_seed_generation_contract_has_no_regression_repair_diff():
    baseline = subprocess.run(
        ["git", "show", f"checkpoint/day13-v1-before-analysis-correction:{SEED_MODULE}"],
        cwd=str(ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    current = (ROOT / SEED_MODULE).read_text(encoding="utf-8")
    assert _locked_seed_generation_ast(current) == _locked_seed_generation_ast(baseline)
    assert set(_locked_seed_generation_ast(current)) == LOCKED_SEED_GENERATION_SYMBOLS


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
