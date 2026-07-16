import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from fastlio2_adapter.detector_output_schema import (
    validate_readonly_detector_output,
)
from fastlio2_adapter.readonly_observation_schema import (
    validate_first_valid_observation_record,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/42_run_harmful_bias_day4_synthetic_adapter.py"
DETECTOR_ARTIFACT = ROOT / "artifacts/current/detector_stage2a"


def load_runner():
    spec = importlib.util.spec_from_file_location("day4_synthetic_runner_pipeline", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_writes_exact_synthetic_contract(tmp_path):
    output_dir = tmp_path / "day4"
    summary = load_runner().run_pipeline(output_dir)
    assert summary["synthetic_only"] is True
    assert summary["real_data_used"] is False
    assert summary["rosbag_run"] is False
    assert summary["fixture_count"] == 3
    for count_field in (
        "adapter_success_count",
        "direct_equivalence_pass_count",
        "input_immutability_pass_count",
        "determinism_pass_count",
        "schema_validation_pass_count",
    ):
        assert summary[count_field] == 3
    assert summary["maximum_direct_equivalence_abs_error"] == 0.0

    expected_files = {
        "synthetic_well_conditioned_observation.json",
        "synthetic_weak_x_observation.json",
        "synthetic_weak_rotated_observation.json",
        "synthetic_well_conditioned_detector_output.json",
        "synthetic_weak_x_detector_output.json",
        "synthetic_weak_rotated_detector_output.json",
        "synthetic_adapter_results.csv",
        "synthetic_adapter_summary.json",
        "SHA256SUMS",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_files


def test_pipeline_records_validate_and_have_no_deferred_information(tmp_path):
    output_dir = tmp_path / "day4"
    load_runner().run_pipeline(output_dir)
    for path in sorted(output_dir.glob("synthetic_*_observation.json")):
        validate_first_valid_observation_record(json.loads(path.read_text()))
    for path in sorted(output_dir.glob("synthetic_*_detector_output.json")):
        validate_readonly_detector_output(json.loads(path.read_text()))
    aggregate = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(output_dir.iterdir())
        if path.suffix in {".json", ".csv"}
    ).lower()
    for token in (
        "auroc",
        "auprc",
        "scientific superiority",
        "harmful-bias detectability",
        "future_frame",
        "holdout_label",
    ):
        assert token not in aggregate


def test_pipeline_is_byte_deterministic_across_directories(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    runner = load_runner()
    runner.run_pipeline(first)
    runner.run_pipeline(second)
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files


def test_sha256sums_verify(tmp_path):
    output_dir = tmp_path / "day4"
    load_runner().run_pipeline(output_dir)
    subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"],
        cwd=output_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def test_cli_exposes_only_output_and_overwrite_options():
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--help"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    help_text = result.stdout
    assert "--output-dir" in help_text
    assert "--overwrite" in help_text
    for option in (
        "--bag",
        "--sequence",
        "--quick",
        "--development",
        "--holdout",
        "--future-test",
        "--retune",
        "--new-threshold",
    ):
        assert option not in help_text


def test_runner_uses_no_random_number_generator():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "np.random" not in source
    assert "random." not in source


def test_pipeline_does_not_modify_frozen_detector_artifact(tmp_path):
    before = tree_hashes(DETECTOR_ARTIFACT)
    load_runner().run_pipeline(tmp_path / "day4")
    after = tree_hashes(DETECTOR_ARTIFACT)
    assert before == after


def tree_hashes(root):
    import hashlib

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
