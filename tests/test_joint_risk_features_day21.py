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

from eval.joint_risk_features import correlation_row, mean_nan_safe, rank_percentile_normalize  # noqa: E402


SCRIPT = ROOT / "scripts/14_joint_risk_features.py"
JOINT_COLUMNS = {
    "joint_risk_equal",
    "joint_risk_spectral",
    "joint_risk_information",
    "joint_risk_odi_information",
    "joint_risk_no_odi",
    "joint_risk_motion_aware",
}
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day21"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day21_script_runs_and_preserves_day18_day20_inputs(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day21_inputs(out_root)
    protected = snapshot_files(out_root)
    config = write_day21_config(tmp_path, n_permutations=25)
    report = tmp_path / "reports/day21_report.md"

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

    features = list(csv.DictReader((out_root / "tables/day21_joint_risk_window_features.csv").open()))
    correlations = list(csv.DictReader((out_root / "tables/day21_joint_risk_correlations.csv").open()))
    controlled = list(csv.DictReader((out_root / "tables/day21_joint_risk_controlled_validity.csv").open()))
    comparison = list(csv.DictReader((out_root / "tables/day21_joint_risk_comparison.csv").open()))
    manifest = json.loads((out_root / "manifests/day21_joint_risk_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert features
    assert correlations
    assert controlled
    assert comparison
    assert JOINT_COLUMNS <= set(features[0].keys())
    assert "joint_risk_no_odi" in {row["feature_name"] for row in comparison}
    assert {"merged", "within_sequence"} <= {row["scope"] for row in correlations}
    assert any(row["beats_no_odi_baseline"] in {"true", "false"} for row in comparison)
    assert any(row["expected_sign_match"] in {"true", "false", "undefined"} for row in correlations)
    assert manifest["status"] == "OK"
    assert manifest["missing_artifacts"] == []
    assert manifest["day21_analysis_passed"] is True
    assert manifest["weak_update_authorized"] is False
    assert "Day 21 does not prove ODI robustness." in report_text
    assert "Day 22 must perform a go/no-go gate review" in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day21_nan_safe_normalization_and_mean():
    ranks = rank_percentile_normalize([np.nan, 2.0, 2.0, 4.0])
    assert np.isnan(ranks[0])
    assert np.all((ranks[1:] >= 0.0) & (ranks[1:] <= 1.0))
    all_nan = rank_percentile_normalize([np.nan, np.nan])
    assert np.all(np.isnan(all_nan))

    values = mean_nan_safe([np.asarray([np.nan, 1.0]), np.asarray([0.5, np.nan])])
    assert np.allclose(values, [0.5, 1.0], equal_nan=False)


def test_day21_small_rho_is_not_substantive():
    rows = [
        {"joint_risk_equal": str(idx), "axis_drift_rate": str((idx % 2) * 0.01)}
        for idx in range(12)
    ]

    row = correlation_row(
        rows,
        "joint_risk_equal",
        "axis_drift_rate",
        "merged",
        "ALL",
        "ALL",
        {"joint_risk_equal": {"axis_drift_rate": "positive"}},
        effect_size_threshold=0.90,
    )

    assert row["passes_effect_size"] == "false"
    assert row["validity_status"] == "exploratory_small_or_wrong_sign"


def test_day21_permutation_seed_is_fixed(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day21_inputs(out_root)
    config = write_day21_config(tmp_path, n_permutations=15)
    command = [
        sys.executable,
        str(SCRIPT),
        "--config",
        str(config),
        "--out-root",
        str(out_root),
        "--report",
        str(tmp_path / "reports/day21_report.md"),
    ]
    run_script(command, tmp_path)
    first = (out_root / "tables/day21_joint_risk_controlled_validity.csv").read_text(encoding="utf-8")
    run_script(command, tmp_path)
    second = (out_root / "tables/day21_joint_risk_controlled_validity.csv").read_text(encoding="utf-8")
    assert first == second


def test_day21_script_reports_missing_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day21_config(tmp_path, n_permutations=5)),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--report",
            str(tmp_path / "reports/day21_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day21 input file" in result.stderr


def prepare_day21_inputs(out_root: Path) -> None:
    tables = out_root / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    write_window_metrics(tables / "day18_window_metrics.csv")
    write_text(tables / "day20_partial_correlations.csv", "metric_name,target_name,partial_spearman_rho\nODI_median,axis_drift_rate,0.01\n")
    write_text(tables / "day20_incremental_validity_summary.csv", "metric_name,target_name,final_day20_status\nODI_median,axis_drift_rate,exploratory_not_validated\n")


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
            condition = 20.0 + idx + seq_idx
            lambda_min = 1.0 / (1.0 + idx + seq_idx)
            ais = 3.0 - 0.04 * idx
            odi = 0.4 + 0.01 * (idx % 4) + 0.002 * seq_idx
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "scene_family": family,
                    "trial_id": idx // 6,
                    "window_id": idx,
                    "start_idx": idx,
                    "end_idx": idx + 5,
                    "path_length": 1.0 + phase,
                    "axis_drift_rate": 0.02 * condition + 0.001 * idx,
                    "cross_drift_rate": 0.01,
                    "weak_drift_alignment": 0.015 * condition + 0.002 * (idx % 2),
                    "ODI_mean": odi,
                    "ODI_median": odi,
                    "AIS_mean": ais,
                    "AIS_median": ais,
                    "lambda_min_clamped_median": lambda_min,
                    "condition_number_median": condition,
                    "weak_alignment_median": np.nan if idx % 5 == 0 else 0.6 + 0.01 * idx,
                    "applied_axis_bias": 0,
                    "is_unbiased_protocol": "true",
                }
            )
    write_csv(path, fieldnames, rows)


def write_day21_config(tmp_path: Path, n_permutations: int) -> Path:
    path = tmp_path / "day21_joint_risk.yaml"
    path.write_text(
        "\n".join(
            [
                "source_validation: day18_day20",
                "targets: [axis_drift_rate, weak_drift_alignment]",
                "base_metrics: [ODI_median, AIS_median, lambda_min_clamped_median, condition_number_median, weak_alignment_median, path_length]",
                "risk_features: [joint_risk_equal, joint_risk_spectral, joint_risk_information, joint_risk_odi_information, joint_risk_no_odi, joint_risk_motion_aware]",
                "normalization: rank_percentile",
                "effect_size_threshold: 0.10",
                f"n_permutations: {int(n_permutations)}",
                "seed: 21000",
                "expected_sign:",
                "  joint_risk_equal: {axis_drift_rate: positive, weak_drift_alignment: positive}",
                "  joint_risk_spectral: {axis_drift_rate: positive, weak_drift_alignment: positive}",
                "  joint_risk_information: {axis_drift_rate: positive, weak_drift_alignment: positive}",
                "  joint_risk_odi_information: {axis_drift_rate: positive, weak_drift_alignment: positive}",
                "  joint_risk_no_odi: {axis_drift_rate: positive, weak_drift_alignment: positive}",
                "  joint_risk_motion_aware: {axis_drift_rate: positive, weak_drift_alignment: positive}",
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
