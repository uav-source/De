"""Day 17 unbiased multi-trial toy-probe utilities."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from eval.metrics import (
    compute_axis_error,
    compute_cumulative_path_length,
    compute_sliding_window_drift_rate,
    load_axis_csv,
    load_tum_pose,
)
from eval.stats import spearman_corr
from minibench.toy_lio import LEGACY_AXIS_BIAS_BY_FAMILY, load_toy_lio_config, run_toy_lio, save_pose_est_tum


ROOT = Path(__file__).resolve().parents[2]
SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]
METRIC_NAMES = [
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
]
TARGET_NAMES = [
    "final_axis_error",
    "axis_drift_rate_median",
]
TRIAL_FIELDNAMES = [
    "sequence_id",
    "scene_family",
    "trial_id",
    "seed",
    "axis_bias_mode",
    "perturbation_profile",
    "legacy_axis_bias",
    "applied_axis_bias",
    "final_axis_error",
    "axis_drift_rate_median",
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
    "weak_alignment_median",
    "is_unbiased_protocol",
]
SUMMARY_FIELDNAMES = [
    "sequence_id",
    "scene_family",
    "n_trials",
    "axis_bias_mode",
    "perturbation_profile",
    "all_applied_axis_bias_zero",
    "final_axis_error_median",
    "final_axis_error_mean",
    "axis_drift_rate_median",
    "axis_drift_rate_mean",
    "ODI_median",
    "AIS_median",
    "lambda_min_clamped_median",
    "condition_number_median",
    "weak_alignment_median",
    "interpretation",
]
CORRELATION_FIELDNAMES = [
    "scope",
    "scene_family",
    "metric_name",
    "target_name",
    "spearman_rho",
    "n",
    "interpretation",
]


def build_trial_schedule(config: Mapping[str, Any], sequences: Sequence[str] = SEQUENCES) -> List[Dict[str, Any]]:
    """Create deterministic sequence/trial/seed rows from the Day 17 config."""

    normalized = load_toy_lio_config(dict(config))
    n_trials = int(normalized.get("n_trials", 1))
    seed = int(normalized.get("seed", 17000))
    seed_stride = int(normalized.get("seed_stride", 37))
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    schedule = []
    for sequence_id in sequences:
        for trial_id in range(n_trials):
            schedule.append(
                {
                    "sequence_id": sequence_id,
                    "trial_id": trial_id,
                    "seed": seed + trial_id * seed_stride,
                    "axis_bias_mode": normalized["axis_bias_mode"],
                    "perturbation_profile": normalized["perturbation_profile"],
                }
            )
    return schedule


def run_unbiased_trials(
    config: Mapping[str, Any],
    data_root: Path,
    day14_results: Path,
    detector_config: Path,
    raw_out: Path,
    sequences: Sequence[str] = SEQUENCES,
) -> List[Dict[str, str]]:
    """Run all Day 17 unbiased toy-probe trials and return trial rows."""

    normalized = load_toy_lio_config(dict(config))
    if normalized["axis_bias_mode"] != "none":
        raise ValueError("Day 17 unbiased probe requires axis_bias_mode='none'")
    raw_out.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, str]] = []
    for item in build_trial_schedule(normalized, sequences):
        sequence_id = str(item["sequence_id"])
        sequence_dir = data_root / sequence_id
        trial_config = dict(normalized)
        trial_config["seed"] = int(item["seed"])
        result = run_toy_lio(sequence_dir, detector_config, trial_config)
        sequence_raw = raw_out / sequence_id
        sequence_raw.mkdir(parents=True, exist_ok=True)
        save_pose_est_tum(result["poses"], sequence_raw / f"trial_{int(item['trial_id']):03d}_pose_est_toy.tum")
        rows.append(build_trial_row(sequence_id, sequence_dir, day14_results, result, trial_config, int(item["trial_id"])))
    return rows


def summarize_trial_results(trial_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Aggregate Day 17 trial rows by sequence."""

    summaries: List[Dict[str, str]] = []
    for sequence_id in SEQUENCES:
        rows = [row for row in trial_rows if row["sequence_id"] == sequence_id]
        if not rows:
            continue
        scene_family = rows[0]["scene_family"]
        final_errors = [float(row["final_axis_error"]) for row in rows]
        drift_rates = [float(row["axis_drift_rate_median"]) for row in rows]
        all_zero = all(abs(float(row["applied_axis_bias"])) < 1.0e-12 for row in rows)
        summaries.append(
            {
                "sequence_id": sequence_id,
                "scene_family": scene_family,
                "n_trials": str(len(rows)),
                "axis_bias_mode": rows[0]["axis_bias_mode"],
                "perturbation_profile": rows[0]["perturbation_profile"],
                "all_applied_axis_bias_zero": str(all_zero).lower(),
                "final_axis_error_median": format_float(statistics.median(final_errors)),
                "final_axis_error_mean": format_float(statistics.fmean(final_errors)),
                "axis_drift_rate_median": format_float(statistics.median(drift_rates)),
                "axis_drift_rate_mean": format_float(statistics.fmean(drift_rates)),
                "ODI_median": rows[0]["ODI_median"],
                "AIS_median": rows[0]["AIS_median"],
                "lambda_min_clamped_median": rows[0]["lambda_min_clamped_median"],
                "condition_number_median": rows[0]["condition_number_median"],
                "weak_alignment_median": rows[0]["weak_alignment_median"],
                "interpretation": "unbiased trial aggregate; exploratory only, not metric validation",
            }
        )
    return summaries


def compute_metric_drift_correlations(trial_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    """Compute merged and per-scene-family exploratory Spearman correlations."""

    outputs: List[Dict[str, str]] = []
    outputs.extend(_correlation_rows("merged", "ALL", trial_rows))
    for scene_family in sorted({row["scene_family"] for row in trial_rows}):
        family_rows = [row for row in trial_rows if row["scene_family"] == scene_family]
        outputs.extend(_correlation_rows("per_scene_family", scene_family, family_rows))
    return outputs


def validate_no_scene_family_bias(trial_rows: Sequence[Mapping[str, str]]) -> bool:
    """Check that all rows are unbiased by construction."""

    return bool(trial_rows) and all(
        row["axis_bias_mode"] == "none"
        and abs(float(row["applied_axis_bias"])) < 1.0e-12
        and row["is_unbiased_protocol"] == "true"
        for row in trial_rows
    )


def write_unbiased_probe_manifest(
    path: Path,
    *,
    config: Mapping[str, Any],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    row_count: int,
    unbiased_protocol_passed: bool,
    no_scene_family_bias_passed: bool,
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    status = "OK" if unbiased_protocol_passed and no_scene_family_bias_passed and not missing else "FAILED"
    manifest = {
        "status": status,
        "git_commit": git_commit(),
        "axis_bias_mode": config.get("axis_bias_mode"),
        "perturbation_profile": config.get("perturbation_profile"),
        "n_trials": int(config.get("n_trials", 1)),
        "seed": int(config.get("seed", 17000)),
        "seed_stride": int(config.get("seed_stride", 37)),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "row_count": int(row_count),
        "unbiased_protocol_passed": bool(unbiased_protocol_passed),
        "no_scene_family_bias_passed": bool(no_scene_family_bias_passed),
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "exploratory evidence only; Day 17 does not validate ODI",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_trial_row(
    sequence_id: str,
    sequence_dir: Path,
    day14_results: Path,
    result: Mapping[str, Any],
    config: Mapping[str, Any],
    trial_id: int,
) -> Dict[str, str]:
    metadata = json.loads((sequence_dir / "scene_metadata.json").read_text(encoding="utf-8"))
    scene_family = str(metadata["scene_family"])
    bias_metadata = result["bias_metadata"]
    est = result["poses"]
    gt = load_tum_pose(sequence_dir / "gt.tum")
    axis = load_axis_csv(sequence_dir / "axis.csv")
    axis_error = compute_axis_error(est, gt, axis)
    path_length = compute_cumulative_path_length(gt)
    windows = compute_sliding_window_drift_rate(axis_error, path_length, window_size=20, stride=5)
    axis_drift_rate_median = float(np.median(windows["drift_rate"])) if windows.shape[0] else 0.0
    spectral = summarize_spectral_metrics(day14_results / "raw" / f"{sequence_id}_odi.csv")
    return {
        "sequence_id": sequence_id,
        "scene_family": scene_family,
        "trial_id": str(int(trial_id)),
        "seed": str(int(config["seed"])),
        "axis_bias_mode": str(config["axis_bias_mode"]),
        "perturbation_profile": str(config["perturbation_profile"]),
        "legacy_axis_bias": format_float(float(LEGACY_AXIS_BIAS_BY_FAMILY[scene_family])),
        "applied_axis_bias": format_float(float(bias_metadata["applied_axis_bias"])),
        "final_axis_error": format_float(float(result["summary"]["final_axis_error"])),
        "axis_drift_rate_median": format_float(axis_drift_rate_median),
        "ODI_median": format_float(spectral["ODI_median"]),
        "AIS_median": format_float(spectral["AIS_median"]),
        "lambda_min_clamped_median": format_float(spectral["lambda_min_clamped_median"]),
        "condition_number_median": format_float(spectral["condition_number_median"]),
        "weak_alignment_median": format_float(spectral["weak_alignment_median"]),
        "is_unbiased_protocol": str(bool(bias_metadata["is_unbiased_protocol"])).lower(),
    }


def summarize_spectral_metrics(path: Path) -> Dict[str, float]:
    values = {
        "ODI": [],
        "AIS": [],
        "lambda_min_clamped": [],
        "condition_number": [],
        "axis_alignment": [],
    }
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for key in values:
                if key in row:
                    value = to_float(row[key])
                    if np.isfinite(value):
                        values[key].append(value)
    return {
        "ODI_median": safe_median(values["ODI"]),
        "AIS_median": safe_median(values["AIS"]),
        "lambda_min_clamped_median": safe_median(values["lambda_min_clamped"]),
        "condition_number_median": safe_median(values["condition_number"]),
        "weak_alignment_median": safe_median(values["axis_alignment"]),
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _correlation_rows(scope: str, scene_family: str, rows: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    outputs: List[Dict[str, str]] = []
    for metric in METRIC_NAMES:
        for target in TARGET_NAMES:
            metric_values = [to_float(row[metric]) for row in rows]
            target_values = [to_float(row[target]) for row in rows]
            rho, _ = spearman_corr(metric_values, target_values)
            outputs.append(
                {
                    "scope": scope,
                    "scene_family": scene_family,
                    "metric_name": metric,
                    "target_name": target,
                    "spearman_rho": format_float(rho),
                    "n": str(finite_pair_count(metric_values, target_values)),
                    "interpretation": correlation_interpretation(scope, rho, metric_values),
                }
            )
    return outputs


def correlation_interpretation(scope: str, rho: float, metric_values: Iterable[float]) -> str:
    values = [value for value in metric_values if np.isfinite(value)]
    if len(values) < 3:
        return "insufficient finite samples; exploratory only"
    if max(values) - min(values) <= 1.0e-12:
        return "undefined because metric is constant in this scope; exploratory only"
    if not np.isfinite(rho):
        return "undefined correlation; exploratory only"
    if scope == "merged":
        return "merged exploratory correlation; can still be influenced by scene-family grouping"
    return "per-scene-family exploratory correlation"


def finite_pair_count(x: Iterable[float], y: Iterable[float]) -> int:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    return int(np.sum(np.isfinite(x_arr) & np.isfinite(y_arr)))


def safe_median(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else float("nan")


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def format_float(value: float) -> str:
    if not np.isfinite(value):
        return "nan"
    if abs(value) < 1.0e-12:
        return "0"
    return f"{float(value):.12g}"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
