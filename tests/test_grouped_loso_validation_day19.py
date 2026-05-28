import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.grouped_loso_validation import compute_grouped_metric_summary  # noqa: E402


SCRIPT = ROOT / "scripts/12_grouped_loso_validation.py"
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]
METRICS = {"ODI_median", "AIS_median", "lambda_min_clamped_median", "condition_number_median"}


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day19"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day19_script_runs_and_preserves_day18_inputs(tmp_path):
    out_root = tmp_path / "results/day30"
    prepare_day18_inputs(out_root)
    protected = snapshot_files(out_root)
    config = write_day19_config(tmp_path)
    report = tmp_path / "reports/day19_report.md"

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

    grouped = list(csv.DictReader((out_root / "tables/day19_grouped_metric_summary.csv").open()))
    loso = list(csv.DictReader((out_root / "tables/day19_loso_selection_results.csv").open()))
    pass_fail = list(csv.DictReader((out_root / "tables/day19_metric_pass_fail_summary.csv").open()))
    manifest = json.loads((out_root / "manifests/day19_grouped_loso_manifest.json").read_text())
    report_text = report.read_text(encoding="utf-8")

    assert grouped
    assert loso
    assert pass_fail
    assert {row["metric_name"] for row in grouped} >= METRICS
    assert {row["held_out_sequence"] for row in loso} == set(SEQUENCES)
    assert manifest["status"] == "OK"
    assert manifest["missing_artifacts"] == []
    assert manifest["day19_validation_passed"] is True
    odi_axis = next(
        row for row in pass_fail if row["metric_name"] == "ODI_median" and row["target_name"] == "axis_drift_rate"
    )
    assert odi_axis["final_day19_status"] == "exploratory_not_validated"
    assert "Day 19 does not authorize weak-subspace update yet." in report_text
    assert "Day 20 must perform controlled / partial validity analysis" in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day19_undefined_metric_not_counted_as_valid():
    rows = [
        {
            "sequence_id": "OC-L0-S01-M1",
            "scene_family": "OC",
            "metric_name": "ODI_median",
            "target_name": "axis_drift_rate",
            "spearman_rho": "nan",
            "validity_status": "undefined_constant_metric",
        },
        {
            "sequence_id": "ST-L3-S01-M1",
            "scene_family": "ST",
            "metric_name": "ODI_median",
            "target_name": "axis_drift_rate",
            "spearman_rho": "0.4",
            "validity_status": "valid",
        },
    ]

    summary = compute_grouped_metric_summary(rows, ["ODI_median"], ["axis_drift_rate"])

    assert summary[0]["n_sequences"] == "2"
    assert summary[0]["n_valid_sequences"] == "1"
    assert summary[0]["n_undefined"] == "1"


def test_day19_script_reports_missing_day18_inputs(tmp_path):
    result = run_script(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(write_day19_config(tmp_path)),
            "--out-root",
            str(tmp_path / "missing_day30"),
            "--report",
            str(tmp_path / "reports/day19_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing required Day19 input file" in result.stderr


def prepare_day18_inputs(out_root: Path) -> None:
    tables = out_root / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    write_window_metrics(tables / "day18_window_metrics.csv")
    write_correlations(tables / "day18_within_sequence_correlations.csv")
    write_sequence_summary(tables / "day18_sequence_validity_summary.csv")


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
        for idx in range(3):
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "scene_family": family,
                    "trial_id": 0,
                    "window_id": idx,
                    "start_idx": idx,
                    "end_idx": idx + 2,
                    "path_length": 1.0,
                    "axis_drift_rate": 0.1 * seq_idx + idx * 0.01,
                    "cross_drift_rate": 0.02,
                    "weak_drift_alignment": 0.8,
                    "ODI_mean": 0.5,
                    "ODI_median": 0.5,
                    "AIS_mean": 1.0,
                    "AIS_median": 1.0,
                    "lambda_min_clamped_median": 0.1,
                    "condition_number_median": 100.0,
                    "weak_alignment_median": 0.9,
                    "applied_axis_bias": 0,
                    "is_unbiased_protocol": "true",
                }
            )
    write_csv(path, fieldnames, rows)


def write_correlations(path: Path) -> None:
    fieldnames = [
        "sequence_id",
        "scene_family",
        "metric_name",
        "target_name",
        "spearman_rho",
        "n_windows",
        "metric_variation",
        "target_variation",
        "validity_status",
        "interpretation",
    ]
    values = {
        "OC-L0-S01-M1": {
            "ODI_median": 0.10,
            "AIS_median": 0.20,
            "lambda_min_clamped_median": 0.05,
            "condition_number_median": 0.03,
        },
        "ST-L3-S01-M1": {
            "ODI_median": 0.08,
            "AIS_median": 0.10,
            "lambda_min_clamped_median": 0.02,
            "condition_number_median": 0.01,
        },
        "CT-L2-S01-M2": {
            "ODI_median": -0.02,
            "AIS_median": 0.03,
            "lambda_min_clamped_median": 0.40,
            "condition_number_median": 0.15,
        },
        "RT-L4-S01-M1": {
            "ODI_median": -0.06,
            "AIS_median": 0.02,
            "lambda_min_clamped_median": "nan",
            "condition_number_median": 0.50,
        },
    }
    rows = []
    for sequence_id in SEQUENCES:
        family = sequence_id.split("-")[0]
        for target in ["axis_drift_rate", "weak_drift_alignment"]:
            for metric in sorted(METRICS):
                rho = values[sequence_id][metric]
                valid = rho != "nan"
                rows.append(
                    {
                        "sequence_id": sequence_id,
                        "scene_family": family,
                        "metric_name": metric,
                        "target_name": target,
                        "spearman_rho": rho,
                        "n_windows": 6 if valid else 0,
                        "metric_variation": 0.1 if valid else 0,
                        "target_variation": 0.1,
                        "validity_status": "valid" if valid else "undefined_constant_metric",
                        "interpretation": "test row",
                    }
                )
    write_csv(path, fieldnames, rows)


def write_sequence_summary(path: Path) -> None:
    fieldnames = [
        "sequence_id",
        "scene_family",
        "n_trials",
        "n_windows",
        "n_valid_correlations",
        "best_metric_for_axis_drift",
        "best_abs_rho_for_axis_drift",
        "ODI_axis_drift_rho",
        "AIS_axis_drift_rho",
        "lambda_min_clamped_axis_drift_rho",
        "condition_number_axis_drift_rho",
        "interpretation",
    ]
    rows = []
    for sequence_id in SEQUENCES:
        rows.append(
            {
                "sequence_id": sequence_id,
                "scene_family": sequence_id.split("-")[0],
                "n_trials": 1,
                "n_windows": 3,
                "n_valid_correlations": 4,
                "best_metric_for_axis_drift": "ODI_median",
                "best_abs_rho_for_axis_drift": 0.1,
                "ODI_axis_drift_rho": 0.1,
                "AIS_axis_drift_rho": 0.2,
                "lambda_min_clamped_axis_drift_rho": 0.05,
                "condition_number_axis_drift_rho": 0.03,
                "interpretation": "test row",
            }
        )
    write_csv(path, fieldnames, rows)


def write_day19_config(tmp_path: Path) -> Path:
    path = tmp_path / "day19_grouped_loso.yaml"
    path.write_text(
        "\n".join(
            [
                "source_validation: day18_within_sequence",
                "targets: [axis_drift_rate, weak_drift_alignment]",
                "metrics: [ODI_median, AIS_median, lambda_min_clamped_median, condition_number_median]",
                "group_keys: [sequence_id, scene_family]",
                "loso_unit: sequence_id",
                "min_valid_sequences: 3",
                "selection_rule: mean_abs_spearman_on_train",
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
