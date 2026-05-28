import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.controlled_partial_validity import (  # noqa: E402
    compute_expected_sign_check,
    residualize_against_controls,
)


SCRIPT = ROOT / "scripts/13_controlled_partial_validity.py"
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]
METRICS = {"ODI_median", "AIS_median", "lambda_min_clamped_median", "condition_number_median"}


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day20"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day20_script_runs_and_preserves_day18_day19_inputs(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day20_inputs(out_root)
    protected = snapshot_files(out_root)
    config = write_day20_config(tmp_path, n_permutations=25)
    report = tmp_path / "reports/day20_report.md"

    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--out-root",
            str(out_root),
            "--report",
            str(report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    partial = list(csv.DictReader((out_root / "tables/day20_partial_correlations.csv").open()))
    regression = list(csv.DictReader((out_root / "tables/day20_controlled_regression_summary.csv").open()))
    permutation = list(csv.DictReader((out_root / "tables/day20_permutation_tests.csv").open()))
    incremental = list(csv.DictReader((out_root / "tables/day20_incremental_validity_summary.csv").open()))
    manifest = json.loads((out_root / "manifests/day20_controlled_partial_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert partial
    assert regression
    assert permutation
    assert incremental
    assert {row["metric_name"] for row in partial} >= METRICS
    assert {"merged_controlled", "within_sequence_controlled"} <= {row["scope"] for row in partial}
    assert manifest["status"] == "OK"
    assert manifest["missing_artifacts"] == []
    assert manifest["day20_analysis_passed"] is True
    odi_axis = next(
        row for row in incremental if row["metric_name"] == "ODI_median" and row["target_name"] == "axis_drift_rate"
    )
    assert odi_axis["final_day20_status"] == "exploratory_not_validated"
    assert "Day 20 does not authorize weak-subspace update unless controlled validity passes." in report_text
    assert "Day 21 must build joint risk features" in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_expected_sign_check_and_small_effect_logic(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day20_inputs(out_root)
    config = write_day20_config(tmp_path, n_permutations=10)
    run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--out-root",
            str(out_root),
            "--report",
            str(tmp_path / "reports/day20_report.md"),
        ],
        tmp_path,
    )

    assert compute_expected_sign_check("positive", 0.2) == "true"
    assert compute_expected_sign_check("positive", -0.2) == "false"
    incremental = list(csv.DictReader((out_root / "tables/day20_incremental_validity_summary.csv").open()))
    assert any(row["passes_effect_size"] == "false" for row in incremental)


def test_degenerate_controls_are_marked_undefined():
    values = np.arange(10, dtype=float)
    duplicate_controls = np.column_stack([np.ones(10), np.ones(10)])

    _, status, n, rank = residualize_against_controls(
        values,
        duplicate_controls,
        min_samples=6,
        prune_degenerate=False,
    )

    assert n == 10
    assert rank < 3
    assert status == "undefined_singular_controls"


def test_day20_permutation_seed_is_fixed(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day20_inputs(out_root)
    config = write_day20_config(tmp_path, n_permutations=15)
    command = [
        sys.executable,
        str(SCRIPT),
        "--config",
        str(config),
        "--out-root",
        str(out_root),
        "--report",
        str(tmp_path / "reports/day20_report.md"),
    ]
    run_script(command, tmp_path)
    first = (out_root / "tables/day20_permutation_tests.csv").read_text(encoding="utf-8")
    run_script(command, tmp_path)
    second = (out_root / "tables/day20_permutation_tests.csv").read_text(encoding="utf-8")

    assert first == second


def test_day20_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day20_config(tmp_path, n_permutations=5)),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--report",
            str(tmp_path / "reports/day20_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day20 input file" in result.stderr


def prepare_day20_inputs(out_root: Path) -> None:
    tables = out_root / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    write_window_metrics(tables / "day18_window_metrics.csv")
    write_text(tables / "day19_grouped_metric_summary.csv", "metric_name,target_name,n_valid_sequences\nODI_median,axis_drift_rate,4\n")
    write_text(tables / "day19_loso_selection_results.csv", "held_out_sequence,target_name,selected_metric_from_train\nOC-L0-S01-M1,axis_drift_rate,ODI_median\n")
    write_text(tables / "day19_metric_pass_fail_summary.csv", "metric_name,target_name,final_day19_status\nODI_median,axis_drift_rate,exploratory_not_validated\n")


def write_window_metrics(path: Path) -> None:
    fieldnames = [
        "sequence_id",
        "scene_family",
        "trial_id",
        "window_id",
        "start_idx",
        "end_idx",
        "path_length",
        "axis_drift_rate",
        "cross_drift_rate",
        "weak_drift_alignment",
        "ODI_mean",
        "ODI_median",
        "AIS_mean",
        "AIS_median",
        "lambda_min_clamped_median",
        "condition_number_median",
        "weak_alignment_median",
        "applied_axis_bias",
        "is_unbiased_protocol",
    ]
    rows = []
    for seq_idx, sequence_id in enumerate(SEQUENCES):
        family = sequence_id.split("-")[0]
        for idx in range(12):
            phase = idx / 11.0
            condition = 10.0 + idx + seq_idx
            lambda_min = 1.0 / (1.0 + idx + seq_idx)
            ais = 2.0 - 0.05 * idx + 0.01 * seq_idx
            odi = 0.5 + 0.005 * ((idx % 3) - 1) + 0.001 * seq_idx
            axis_target = 0.05 * condition - 0.02 * lambda_min + 0.001 * idx
            weak_target = 0.04 * condition + 0.002 * (idx % 2)
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "scene_family": family,
                    "trial_id": idx // 6,
                    "window_id": idx,
                    "start_idx": idx,
                    "end_idx": idx + 5,
                    "path_length": 1.0 + phase,
                    "axis_drift_rate": axis_target,
                    "cross_drift_rate": 0.01 + 0.001 * idx,
                    "weak_drift_alignment": weak_target,
                    "ODI_mean": odi,
                    "ODI_median": odi,
                    "AIS_mean": ais,
                    "AIS_median": ais,
                    "lambda_min_clamped_median": lambda_min,
                    "condition_number_median": condition,
                    "weak_alignment_median": 0.7 + 0.01 * (idx % 4),
                    "applied_axis_bias": 0,
                    "is_unbiased_protocol": "true",
                }
            )
    write_csv(path, fieldnames, rows)


def write_day20_config(tmp_path: Path, n_permutations: int) -> Path:
    path = tmp_path / "day20_controlled_partial.yaml"
    path.write_text(
        "\n".join(
            [
                "source_validation: day18_day19",
                "targets: [axis_drift_rate, weak_drift_alignment]",
                "metrics: [ODI_median, AIS_median, lambda_min_clamped_median, condition_number_median]",
                "controls: [AIS_median, lambda_min_clamped_median, condition_number_median, weak_alignment_median, path_length]",
                "group_controls: [sequence_id, scene_family]",
                "effect_size_threshold: 0.10",
                f"n_permutations: {int(n_permutations)}",
                "seed: 20000",
                "expected_sign:",
                "  ODI_median:",
                "    axis_drift_rate: positive",
                "    weak_drift_alignment: positive",
                "  condition_number_median:",
                "    axis_drift_rate: positive",
                "    weak_drift_alignment: positive",
                "  AIS_median:",
                "    axis_drift_rate: negative",
                "    weak_drift_alignment: negative",
                "  lambda_min_clamped_median:",
                "    axis_drift_rate: negative",
                "    weak_drift_alignment: negative",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_csv(path: Path, fieldnames, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot_files(root: Path):
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def run_script(command, tmp_path: Path, check: bool = True):
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=child_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
    if check:
        result.check_returncode()
    return result
