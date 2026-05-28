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

from eval.within_sequence_validation import compute_within_sequence_correlations  # noqa: E402


DAY17_SCRIPT = ROOT / "scripts/10_unbiased_metric_probe.py"
DAY18_SCRIPT = ROOT / "scripts/11_within_sequence_validation.py"
DETECTOR_CONFIG = ROOT / "configs/detector/odi_default.yaml"
SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]
REQUIRED_METRICS = {"ODI_median", "AIS_median", "lambda_min_clamped_median", "condition_number_median"}


def child_env(tmp_path: Path):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig_day18"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def test_day18_script_runs_and_preserves_prior_outputs(tmp_path, day14_tmp_pipeline):
    data_root = day14_tmp_pipeline["data_root"]
    day14_results = prepare_day14_inputs(tmp_path, data_root)
    out_root = tmp_path / "results/day30"
    prepare_day15_day16_inputs(out_root)
    day17_config = write_day17_config(tmp_path, n_trials=2)
    day17_report = tmp_path / "reports/day17_report.md"

    run_script(
        [
            sys.executable,
            str(DAY17_SCRIPT),
            "--config",
            str(day17_config),
            "--detector-config",
            str(DETECTOR_CONFIG),
            "--data-root",
            str(data_root),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(day17_report),
        ],
        tmp_path,
    )

    protected = snapshot_files(day14_results)
    protected.update(snapshot_files(out_root))
    day18_config = write_day18_config(tmp_path)
    day18_report = tmp_path / "reports/day18_report.md"
    result = run_script(
        [
            sys.executable,
            str(DAY18_SCRIPT),
            "--config",
            str(day18_config),
            "--data-root",
            str(data_root),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(day18_report),
        ],
        tmp_path,
    )

    assert result.returncode == 0
    for path, content in protected.items():
        assert path.read_bytes() == content

    windows = list(csv.DictReader((out_root / "tables/day18_window_metrics.csv").open()))
    correlations = list(csv.DictReader((out_root / "tables/day18_within_sequence_correlations.csv").open()))
    summary = list(csv.DictReader((out_root / "tables/day18_sequence_validity_summary.csv").open()))
    manifest = json.loads((out_root / "manifests/day18_within_sequence_manifest.json").read_text())
    report_text = day18_report.read_text(encoding="utf-8")

    assert windows
    assert correlations
    assert summary
    assert {row["applied_axis_bias"] for row in windows} == {"0"}
    assert {row["is_unbiased_protocol"] for row in windows} == {"true"}
    assert {row["metric_name"] for row in correlations} >= REQUIRED_METRICS
    assert {"axis_drift_rate", "weak_drift_alignment"} <= {row["target_name"] for row in correlations}
    assert manifest["status"] == "OK"
    assert manifest["all_unbiased_protocol"] is True
    assert manifest["within_sequence_validation_passed"] is True
    assert manifest["missing_artifacts"] == []
    assert "Day 18 does not yet prove ODI robustness." in report_text
    assert "Day 19 must perform grouped / LOSO validation" in report_text
    assert "ODI " + "robustly predicts drift" not in report_text


def test_day18_constant_metric_is_marked_undefined():
    rows = []
    for idx in range(6):
        rows.append(
            {
                "sequence_id": "OC-L0-S01-M1",
                "scene_family": "OC",
                "ODI_median": "0.5",
                "AIS_median": str(1.0 + idx),
                "lambda_min_clamped_median": "2.0",
                "condition_number_median": "10.0",
                "axis_drift_rate": str(0.01 * idx),
                "weak_drift_alignment": str(0.2 + 0.01 * idx),
            }
        )

    correlations = compute_within_sequence_correlations(
        rows,
        metrics=["ODI", "AIS"],
        targets=["axis_drift_rate"],
        min_windows_per_sequence=3,
    )

    status_by_metric = {row["metric_name"]: row["validity_status"] for row in correlations}
    assert status_by_metric["ODI_median"] == "undefined_constant_metric"
    assert status_by_metric["AIS_median"] == "valid"
    odi_row = next(row for row in correlations if row["metric_name"] == "ODI_median")
    assert odi_row["spearman_rho"] == "nan"


def test_day18_script_reports_missing_day17_raw_trajectory(tmp_path, day14_tmp_pipeline):
    data_root = day14_tmp_pipeline["data_root"]
    day14_results = prepare_day14_inputs(tmp_path, data_root)
    out_root = tmp_path / "results/day30"
    prepare_day15_day16_inputs(out_root)
    day17_config = write_day17_config(tmp_path, n_trials=1)
    run_script(
        [
            sys.executable,
            str(DAY17_SCRIPT),
            "--config",
            str(day17_config),
            "--detector-config",
            str(DETECTOR_CONFIG),
            "--data-root",
            str(data_root),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(tmp_path / "reports/day17_report.md"),
        ],
        tmp_path,
    )
    missing_pose = out_root / "raw/unbiased_day17/OC-L0-S01-M1/trial_000_pose_est_toy.tum"
    missing_pose.unlink()

    result = run_script(
        [
            sys.executable,
            str(DAY18_SCRIPT),
            "--config",
            str(write_day18_config(tmp_path)),
            "--data-root",
            str(data_root),
            "--day14-results",
            str(day14_results),
            "--out-root",
            str(out_root),
            "--report",
            str(tmp_path / "reports/day18_report.md"),
        ],
        tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "Missing Day 17 raw trajectory" in result.stderr


def prepare_day14_inputs(tmp_path: Path, data_root: Path) -> Path:
    results = tmp_path / "results/day14"
    raw = results / "raw"
    tables = results / "tables"
    raw.mkdir(parents=True)
    tables.mkdir(parents=True)
    for seq_idx, sequence_id in enumerate(SEQUENCES):
        timestamps = np.loadtxt(data_root / sequence_id / "gt.tum")[:, 0]
        write_odi(raw / f"{sequence_id}_odi.csv", timestamps, seq_idx)
    write_text(tables / "day10_metric_validity_per_sequence.csv", "sequence_id,metric_name,target_name,spearman_rho\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    write_text(tables / "day10_metric_validity_loso.csv", "held_out_sequence,metric_name,target_name,test_spearman_rho_or_auc\nST-L3-S01-M1,ODI,axis_drift_rate,-0.1\n")
    return results


def prepare_day15_day16_inputs(out_root: Path) -> None:
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "manifests").mkdir(parents=True, exist_ok=True)
    write_text(out_root / "tables/day15_bias_audit.csv", "sequence_id,confound_risk_level\nST-L3-S01-M1,HIGH\n")
    write_text(out_root / "manifests/day15_bias_audit_manifest.json", '{"status":"OK"}\n')
    write_text(out_root / "tables/day16_unbiased_toy_lio_summary.csv", "sequence_id,axis_bias_mode,applied_axis_bias\nST-L3-S01-M1,none,0\n")
    write_text(out_root / "manifests/day16_unbiased_toy_lio_manifest.json", '{"status":"OK"}\n')


def write_day17_config(tmp_path: Path, n_trials: int) -> Path:
    path = tmp_path / "unbiased_day17_test.yaml"
    path.write_text(
        "\n".join(
            [
                "axis_bias_mode: none",
                "perturbation_profile: unbiased_day17",
                f"n_trials: {int(n_trials)}",
                "seed: 17000",
                "seed_stride: 37",
                "notes: test config",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_day18_config(tmp_path: Path) -> Path:
    path = tmp_path / "day18_within_sequence.yaml"
    path.write_text(
        "\n".join(
            [
                "source_probe: day17_unbiased",
                "window_size: 8",
                "stride: 4",
                "min_windows_per_sequence: 3",
                "metrics: [ODI, AIS, lambda_min_clamped, condition_number, weak_alignment]",
                "targets: [axis_drift_rate, cross_drift_rate, weak_drift_alignment]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_odi(path: Path, timestamps, seq_idx: int) -> None:
    fieldnames = [
        "timestamp",
        "ODI",
        "AIS",
        "lambda_min",
        "lambda_min_clamped",
        "condition_number",
        "axis_alignment",
        "weak_reliable",
        "weak_trans_x",
        "weak_trans_y",
        "weak_trans_z",
    ]
    rows = []
    for frame, timestamp in enumerate(timestamps):
        tunnel = seq_idx > 0
        rows.append(
            {
                "timestamp": float(timestamp),
                "ODI": 0.3 + 0.001 * frame if not tunnel else 0.72 + 0.002 * frame + 0.01 * seq_idx,
                "AIS": 9.0 - 0.001 * frame - 0.2 * seq_idx,
                "lambda_min": 1.0 / (frame + 1.0) if not tunnel else 0.001 * (frame + 1.0),
                "lambda_min_clamped": 1.0 / (frame + 1.0) if not tunnel else 0.001 * (frame + 1.0),
                "condition_number": 20.0 + frame if not tunnel else 600.0 + 2.0 * frame,
                "axis_alignment": np.nan if not tunnel else 0.9 + 0.001 * (frame % 10),
                "weak_reliable": 0 if not tunnel else 1,
                "weak_trans_x": 1.0,
                "weak_trans_y": 0.0,
                "weak_trans_z": 0.0,
            }
        )
    write_csv(path, fieldnames, rows)


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
