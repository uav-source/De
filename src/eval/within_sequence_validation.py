"""Day 18 window-level within-sequence validation utilities."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from degen_detector.weak_direction import compute_drift_alignment
from eval.metrics import (
    compute_axis_error,
    compute_cross_error,
    compute_cumulative_path_length,
    compute_sliding_window_drift_rate,
    load_axis_csv,
    load_tum_pose,
)
from eval.stats import spearman_corr


ROOT = Path(__file__).resolve().parents[2]
SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]

METRIC_FIELD_MAP = {
    "ODI": "ODI_median",
    "AIS": "AIS_median",
    "lambda_min_clamped": "lambda_min_clamped_median",
    "condition_number": "condition_number_median",
    "weak_alignment": "weak_alignment_median",
}

TARGET_FIELD_MAP = {
    "axis_drift_rate": "axis_drift_rate",
    "cross_drift_rate": "cross_drift_rate",
    "weak_drift_alignment": "weak_drift_alignment",
}

WINDOW_FIELDNAMES = [
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

CORRELATION_FIELDNAMES = [
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

SUMMARY_FIELDNAMES = [
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


def load_day17_probe_inputs(
    config: Mapping[str, Any],
    data_root: Path,
    day14_results: Path,
    day30_root: Path,
) -> Dict[str, Any]:
    """Load Day 17 trial rows and verify all raw trajectories are present."""

    trials_path = day30_root / "tables/day17_unbiased_probe_trials.csv"
    if not trials_path.exists():
        raise FileNotFoundError(f"Missing Day 17 probe table: {trials_path}. Run Day 17 first.")

    trial_rows = read_csv_rows(trials_path)
    if not trial_rows:
        raise ValueError(f"Day 17 probe table is empty: {trials_path}")

    inputs: List[Path] = [trials_path]
    missing: List[str] = []
    for sequence_id in SEQUENCES:
        sequence_dir = data_root / sequence_id
        for name in ["gt.tum", "axis.csv"]:
            path = sequence_dir / name
            inputs.append(path)
            if not path.exists():
                missing.append(str(path))
        odi_path = day14_results / "raw" / f"{sequence_id}_odi.csv"
        inputs.append(odi_path)
        if not odi_path.exists():
            missing.append(str(odi_path))

    raw_root = day30_root / "raw/unbiased_day17"
    for row in trial_rows:
        pose_path = trial_pose_path(raw_root, row["sequence_id"], int(row["trial_id"]))
        inputs.append(pose_path)
        if not pose_path.exists():
            missing.append(
                f"Missing Day 17 raw trajectory: {pose_path}. "
                "Run scripts/10_unbiased_metric_probe.py before Day 18."
            )

    if missing:
        raise FileNotFoundError("Missing required Day18 input file(s): " + "; ".join(missing))

    return {
        "config": dict(config),
        "trial_rows": trial_rows,
        "inputs": inputs,
        "data_root": data_root,
        "day14_results": day14_results,
        "day30_root": day30_root,
    }


def build_window_level_table(
    inputs: Mapping[str, Any],
    window_size: int,
    stride: int,
) -> List[Dict[str, str]]:
    """Build one row per sequence/trial/window from saved Day 17 TUM files."""

    data_root = Path(inputs["data_root"])
    day14_results = Path(inputs["day14_results"])
    raw_root = Path(inputs["day30_root"]) / "raw/unbiased_day17"
    sequence_cache: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, str]] = []

    for trial in inputs["trial_rows"]:
        sequence_id = trial["sequence_id"]
        if sequence_id not in sequence_cache:
            sequence_cache[sequence_id] = load_sequence_data(sequence_id, data_root, day14_results)
        seq = sequence_cache[sequence_id]
        est = load_tum_pose(trial_pose_path(raw_root, sequence_id, int(trial["trial_id"])))
        rows.extend(
            build_trial_windows(
                sequence_id=sequence_id,
                scene_family=trial["scene_family"],
                trial_id=int(trial["trial_id"]),
                est=est,
                gt=seq["gt"],
                axis=seq["axis"],
                odi_table=seq["odi"],
                applied_axis_bias=trial["applied_axis_bias"],
                is_unbiased_protocol=trial["is_unbiased_protocol"],
                window_size=window_size,
                stride=stride,
            )
        )
    return rows


def compute_window_drift_targets(
    est: np.ndarray,
    gt: np.ndarray,
    axis: np.ndarray,
    window_size: int,
    stride: int,
) -> Dict[str, Any]:
    """Compute axis/cross drift and weak-drift vectors for sliding windows."""

    axis_error = compute_axis_error(est, gt, axis)
    cross_error = compute_cross_error(est, gt, axis)
    path_length = compute_cumulative_path_length(gt)
    axis_windows = compute_sliding_window_drift_rate(axis_error, path_length, window_size, stride)
    cross_windows = compute_sliding_window_drift_rate(cross_error, path_length, window_size, stride)
    translation_error = est[:, 1:4] - gt[:, 1:4]
    return {
        "axis_windows": axis_windows,
        "cross_windows": cross_windows,
        "translation_error": translation_error,
    }


def attach_window_spectral_metrics(
    odi_table: Mapping[str, np.ndarray],
    start_idx: int,
    end_idx: int,
) -> Dict[str, float]:
    """Summarize detector metrics over one frame window."""

    sl = slice(int(start_idx), int(end_idx) + 1)
    lambda_min_clamped = odi_table.get("lambda_min_clamped")
    if lambda_min_clamped is None:
        lambda_min_clamped = np.maximum(np.asarray(odi_table["lambda_min"], dtype=float), 0.0)
    axis_alignment = np.asarray(odi_table.get("axis_alignment", np.full_like(odi_table["ODI"], np.nan)), dtype=float)
    return {
        "ODI_mean": float(np.mean(odi_table["ODI"][sl])),
        "ODI_median": float(np.median(odi_table["ODI"][sl])),
        "AIS_mean": float(np.mean(odi_table["AIS"][sl])),
        "AIS_median": float(np.median(odi_table["AIS"][sl])),
        "lambda_min_clamped_median": float(np.median(lambda_min_clamped[sl])),
        "condition_number_median": float(np.median(odi_table["condition_number"][sl])),
        "weak_alignment_median": safe_nanmedian(axis_alignment[sl]),
    }


def compute_within_sequence_correlations(
    window_rows: Sequence[Mapping[str, str]],
    metrics: Sequence[str],
    targets: Sequence[str],
    min_windows_per_sequence: int,
) -> List[Dict[str, str]]:
    """Compute Spearman correlations within each sequence only."""

    metric_fields = [METRIC_FIELD_MAP.get(metric, metric) for metric in metrics]
    target_fields = [TARGET_FIELD_MAP.get(target, target) for target in targets]
    outputs: List[Dict[str, str]] = []
    for sequence_id in SEQUENCES:
        rows = [row for row in window_rows if row["sequence_id"] == sequence_id]
        if not rows:
            continue
        scene_family = rows[0]["scene_family"]
        for metric in metric_fields:
            for target in target_fields:
                metric_values = [to_float(row.get(metric)) for row in rows]
                target_values = [to_float(row.get(target)) for row in rows]
                n = finite_pair_count(metric_values, target_values)
                metric_variation = finite_variation(metric_values)
                target_variation = finite_variation(target_values)
                status = correlation_status(n, metric_variation, target_variation, min_windows_per_sequence)
                rho = float("nan")
                if status == "valid":
                    rho, _ = spearman_corr(metric_values, target_values)
                    if not np.isfinite(rho):
                        status = "undefined"
                outputs.append(
                    {
                        "sequence_id": sequence_id,
                        "scene_family": scene_family,
                        "metric_name": metric,
                        "target_name": target,
                        "spearman_rho": format_float(rho),
                        "n_windows": str(n),
                        "metric_variation": format_float(metric_variation),
                        "target_variation": format_float(target_variation),
                        "validity_status": status,
                        "interpretation": correlation_interpretation(metric, target, status),
                    }
                )
    return outputs


def compute_sequence_aggregate_validity(
    window_rows: Sequence[Mapping[str, str]],
    correlation_rows: Sequence[Mapping[str, str]],
) -> List[Dict[str, str]]:
    """Summarize per-sequence window validation results."""

    outputs: List[Dict[str, str]] = []
    axis_metrics = [
        "ODI_median",
        "AIS_median",
        "lambda_min_clamped_median",
        "condition_number_median",
    ]
    summary_names = {
        "ODI_median": "ODI_axis_drift_rho",
        "AIS_median": "AIS_axis_drift_rho",
        "lambda_min_clamped_median": "lambda_min_clamped_axis_drift_rho",
        "condition_number_median": "condition_number_axis_drift_rho",
    }
    for sequence_id in SEQUENCES:
        rows = [row for row in window_rows if row["sequence_id"] == sequence_id]
        corr = [row for row in correlation_rows if row["sequence_id"] == sequence_id]
        if not rows:
            continue
        axis_corr = {
            row["metric_name"]: row
            for row in corr
            if row["target_name"] == "axis_drift_rate" and row["metric_name"] in axis_metrics
        }
        valid = [row for row in corr if row["validity_status"] == "valid"]
        best_metric = "none"
        best_abs = float("nan")
        for metric in axis_metrics:
            rho = to_float(axis_corr.get(metric, {}).get("spearman_rho"))
            if np.isfinite(rho) and (not np.isfinite(best_abs) or abs(rho) > best_abs):
                best_metric = metric
                best_abs = abs(rho)
        output = {
            "sequence_id": sequence_id,
            "scene_family": rows[0]["scene_family"],
            "n_trials": str(len({row["trial_id"] for row in rows})),
            "n_windows": str(len(rows)),
            "n_valid_correlations": str(len(valid)),
            "best_metric_for_axis_drift": best_metric,
            "best_abs_rho_for_axis_drift": format_float(best_abs),
            "interpretation": sequence_interpretation(best_metric, axis_corr),
        }
        for metric, name in summary_names.items():
            output[name] = axis_corr.get(metric, {}).get("spearman_rho", "nan")
        outputs.append(output)
    return outputs


def write_day18_manifest(
    path: Path,
    *,
    config: Mapping[str, Any],
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    row_count: int,
    sequence_count: int,
    all_unbiased_protocol: bool,
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    validation_passed = bool(all_unbiased_protocol and row_count > 0 and sequence_count > 0 and not missing)
    manifest = {
        "status": "OK" if validation_passed else "FAILED",
        "git_commit": git_commit(),
        "source_probe": config.get("source_probe", "day17_unbiased"),
        "window_size": int(config.get("window_size", 20)),
        "stride": int(config.get("stride", 5)),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "row_count": int(row_count),
        "sequence_count": int(sequence_count),
        "all_unbiased_protocol": bool(all_unbiased_protocol),
        "within_sequence_validation_passed": validation_passed,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "window-level within-sequence validation completed; this does not prove ODI robustness",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_sequence_data(sequence_id: str, data_root: Path, day14_results: Path) -> Dict[str, Any]:
    seq_dir = data_root / sequence_id
    gt = load_tum_pose(seq_dir / "gt.tum")
    axis = load_axis_csv(seq_dir / "axis.csv")
    odi = load_odi_csv(day14_results / "raw" / f"{sequence_id}_odi.csv")
    if gt.shape[0] != axis.shape[0]:
        raise ValueError(f"Axis count does not match GT count: {seq_dir}")
    if odi["ODI"].shape[0] != gt.shape[0]:
        raise ValueError(f"ODI row count does not match GT count: {day14_results / 'raw' / f'{sequence_id}_odi.csv'}")
    if "timestamp" in odi and not np.allclose(odi["timestamp"], gt[:, 0], atol=1.0e-6, rtol=0.0):
        raise ValueError(f"ODI timestamps do not match GT: {day14_results / 'raw' / f'{sequence_id}_odi.csv'}")
    return {"gt": gt, "axis": axis, "odi": odi}


def build_trial_windows(
    *,
    sequence_id: str,
    scene_family: str,
    trial_id: int,
    est: np.ndarray,
    gt: np.ndarray,
    axis: np.ndarray,
    odi_table: Mapping[str, np.ndarray],
    applied_axis_bias: str,
    is_unbiased_protocol: str,
    window_size: int,
    stride: int,
) -> List[Dict[str, str]]:
    targets = compute_window_drift_targets(est, gt, axis, window_size, stride)
    rows: List[Dict[str, str]] = []
    axis_windows = targets["axis_windows"]
    cross_windows = targets["cross_windows"]
    translation_error = targets["translation_error"]
    for window_id, (axis_row, cross_row) in enumerate(zip(axis_windows, cross_windows)):
        start = int(axis_row["start_idx"])
        end = int(axis_row["end_idx"])
        weak_trans = representative_weak_translation(odi_table, start, end)
        drift_vector = translation_error[end] - translation_error[start]
        spectral = attach_window_spectral_metrics(odi_table, start, end)
        row = {
            "sequence_id": sequence_id,
            "scene_family": scene_family,
            "trial_id": str(int(trial_id)),
            "window_id": str(int(window_id)),
            "start_idx": str(start),
            "end_idx": str(end),
            "path_length": format_float(float(axis_row["path_length"])),
            "axis_drift_rate": format_float(float(axis_row["drift_rate"])),
            "cross_drift_rate": format_float(float(cross_row["drift_rate"])),
            "weak_drift_alignment": format_float(compute_drift_alignment(weak_trans, drift_vector)),
            "applied_axis_bias": format_float(to_float(applied_axis_bias)),
            "is_unbiased_protocol": str(is_unbiased_protocol).lower(),
        }
        row.update({key: format_float(value) for key, value in spectral.items()})
        rows.append(row)
    return rows


def load_odi_csv(path: Path) -> Dict[str, np.ndarray]:
    rows = read_csv_rows(path)
    if not rows:
        raise ValueError(f"ODI CSV has no rows: {path}")
    columns: Dict[str, np.ndarray] = {}
    for key in rows[0].keys():
        values = [to_float(row.get(key)) for row in rows]
        columns[key] = np.asarray(values, dtype=float)
    for key in ["timestamp", "ODI", "AIS", "condition_number"]:
        if key not in columns:
            raise ValueError(f"ODI CSV missing required column {key}: {path}")
    if "lambda_min_clamped" not in columns:
        if "lambda_min" not in columns:
            raise ValueError(f"ODI CSV missing lambda_min_clamped/lambda_min: {path}")
        columns["lambda_min_clamped"] = np.maximum(columns["lambda_min"], 0.0)
    return columns


def representative_weak_translation(odi_table: Mapping[str, np.ndarray], start: int, end: int) -> np.ndarray:
    required = ["weak_trans_x", "weak_trans_y", "weak_trans_z"]
    if any(key not in odi_table for key in required):
        return np.full(3, np.nan, dtype=float)
    weak = np.column_stack([odi_table[key][start : end + 1] for key in required])
    if "weak_reliable" in odi_table:
        reliable = np.asarray(odi_table["weak_reliable"][start : end + 1], dtype=float) > 0.5
        weak = weak[reliable]
    finite = weak[np.all(np.isfinite(weak), axis=1)]
    if finite.size == 0:
        return np.full(3, np.nan, dtype=float)
    vector = np.nanmedian(finite, axis=0)
    norm = float(np.linalg.norm(vector))
    if norm < 1.0e-12:
        return np.full(3, np.nan, dtype=float)
    return vector / norm


def trial_pose_path(raw_root: Path, sequence_id: str, trial_id: int) -> Path:
    return raw_root / sequence_id / f"trial_{int(trial_id):03d}_pose_est_toy.tum"


def correlation_status(n: int, metric_variation: float, target_variation: float, min_windows: int) -> str:
    if n < max(3, int(min_windows)):
        return "insufficient_windows"
    if not np.isfinite(metric_variation) or metric_variation <= 1.0e-12:
        return "undefined_constant_metric"
    if not np.isfinite(target_variation) or target_variation <= 1.0e-12:
        return "undefined_constant_target"
    return "valid"


def correlation_interpretation(metric: str, target: str, status: str) -> str:
    if status == "valid":
        return f"within-sequence window-level association for {metric} vs {target}; exploratory, not proof"
    if status == "undefined_constant_metric":
        return "metric is effectively constant within this sequence; rho is not interpretable"
    if status == "undefined_constant_target":
        return "target is effectively constant within this sequence; rho is not interpretable"
    if status == "insufficient_windows":
        return "not enough finite windows for within-sequence correlation"
    return "undefined correlation; do not use as evidence"


def sequence_interpretation(best_metric: str, axis_corr: Mapping[str, Mapping[str, str]]) -> str:
    odi_rho = to_float(axis_corr.get("ODI_median", {}).get("spearman_rho"))
    if best_metric == "none":
        return "no valid axis-drift correlation; metric constancy or insufficient variation limits validation"
    if best_metric == "ODI_median" and np.isfinite(odi_rho):
        return "ODI is strongest for axis drift in this sequence only; not a cross-sequence claim"
    return f"{best_metric} is strongest for axis drift in this sequence; ODI is not uniquely supported"


def finite_variation(values: Iterable[float]) -> float:
    array = np.asarray([float(value) for value in values], dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return float("nan")
    return float(np.max(finite) - np.min(finite))


def finite_pair_count(x: Iterable[float], y: Iterable[float]) -> int:
    x_arr = np.asarray(list(x), dtype=float)
    y_arr = np.asarray(list(y), dtype=float)
    return int(np.sum(np.isfinite(x_arr) & np.isfinite(y_arr)))


def safe_nanmedian(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite))


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def all_rows_unbiased(rows: Sequence[Mapping[str, str]]) -> bool:
    return bool(rows) and all(
        abs(to_float(row.get("applied_axis_bias"))) < 1.0e-12
        and str(row.get("is_unbiased_protocol", "")).lower() == "true"
        for row in rows
    )


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


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def format_float(value: float) -> str:
    if not np.isfinite(value):
        return "nan"
    if abs(value) < 1.0e-12:
        return "0"
    return f"{float(value):.12g}"
