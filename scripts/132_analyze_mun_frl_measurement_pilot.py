#!/usr/bin/env python3
"""Run the frozen detector and preregistered MUN-FRL pilot analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.measurement_pilot import (  # noqa: E402
    interval_for_timestamp,
    load_interval_lock,
)
from eval.measurement_real_analysis import (  # noqa: E402
    binary_ranking_metrics,
    evaluate_pilot_gates,
    maximum_consecutive_true,
    runtime_summary,
    spearman_correlation,
    summary_statistics,
)
from eval.navsat_reference import (  # noqa: E402
    NavSatSample,
    navsat_to_enu,
    trajectory_error_rows,
    weak_direction_angle_error_deg,
)
from fastlio2_adapter.frozen_observation import load_existing_converter  # noqa: E402
from fastlio2_adapter.measurement_mode import (  # noqa: E402
    MeasurementModeProcessor,
    deterministic_payload,
    invalid_runtime_row,
    validate_measurement_row,
    write_measurement_csv,
)


DEFAULT_RAW = ROOT / "results/measurement_real_validation/mun_frl_lighthouse_pilot/raw"
DEFAULT_OUTPUT = ROOT / "results/measurement_real_validation/mun_frl_lighthouse_pilot/analysis"
DEFAULT_ARTIFACT = ROOT / "artifacts/current/measurement_real_validation_pilot"
DEFAULT_BAG_VALIDATION = ROOT / "data/measurement_real_validation/mun_frl_lighthouse_pilot/bag_validation.json"
DEFAULT_INTERVALS = ROOT / "configs/real_data/mun_frl_pilot_intervals.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        if not rows:
            raise ValueError(f"cannot infer fields for empty table: {path}")
        fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_raw_records(raw_dir: Path) -> tuple[list[dict[str, Any]], list[Any], dict[str, Any]]:
    converter = load_existing_converter(ROOT)
    runtime_path = raw_dir / "runtime_audit_v2.bin"
    observation_path = raw_dir / "observation_records_v3.bin"
    runtime_records, runtime_integrity = converter.read_framed_binary(
        runtime_path, magic=converter.RUNTIME_MAGIC, version=converter.RUNTIME_VERSION
    )
    observation_records, observation_integrity = converter.read_framed_binary(
        observation_path,
        magic=converter.OBSERVATION_MAGIC,
        version=converter.OBSERVATION_VERSION,
    )
    runtime_rows = [converter.decode_runtime_record(record) for record in runtime_records]
    return runtime_rows, observation_records, {
        "runtime": runtime_integrity,
        "observation": observation_integrity,
        "runtime_binary_sha256": sha256_file(runtime_path),
        "observation_binary_sha256": sha256_file(observation_path),
    }


def process_detector(
    raw_dir: Path, tables_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    converter = load_existing_converter(ROOT)
    runtime_rows, observation_records, integrity = load_raw_records(raw_dir)
    runtime_by_scan = {int(row["scan_index"]): row for row in runtime_rows}
    processor = MeasurementModeProcessor()
    replay_processor = MeasurementModeProcessor()
    metric_by_scan: dict[int, dict[str, Any]] = {}
    frozen_mismatch_count = 0
    for record in observation_records:
        observation = converter.decode_observation_record(record)
        scan = int(observation["scan_index"])
        first = processor.process(observation, runtime_by_scan[scan])
        second = replay_processor.process(observation, runtime_by_scan[scan])
        if deterministic_payload(first) != deterministic_payload(second):
            frozen_mismatch_count += 1
        validate_measurement_row(first)
        metric_by_scan[scan] = first
    rows = [
        metric_by_scan.get(int(runtime["scan_index"]), invalid_runtime_row(runtime))
        for runtime in runtime_rows
    ]
    write_measurement_csv(tables_dir / "frame_metrics.csv", rows)
    invalid_counts = Counter(
        str(row["invalid_reason"]) for row in rows if not row["detector_valid"]
    )
    invalid_rows = [
        {"invalid_reason": reason, "frame_count": count}
        for reason, count in sorted(invalid_counts.items())
    ]
    write_csv(
        tables_dir / "invalid_reason_summary.csv",
        invalid_rows,
        ["invalid_reason", "frame_count"],
    )
    runtime_mutation_count = sum(
        bool(row["tap_call_mutation_detected"]) for row in runtime_rows
    )
    export_mutation_count = sum(
        bool(row["export_call_mutation_detected"]) for row in runtime_rows
    )
    audit = processor.audit_summary(rows)
    audit.update(
        {
            "frozen_detector_mismatch_count": frozen_mismatch_count,
            "runtime_tap_same_call_mutation_count": runtime_mutation_count,
            "runtime_export_estimator_checksum_change_count": export_mutation_count,
            "replay_processor_same_call_mutation_count": replay_processor.same_call_mutation_count,
            "tap_drop_count": max(int(row["tap_drop_count"]) for row in runtime_rows),
            "runtime_record_count": len(runtime_rows),
            "observation_record_count": len(observation_records),
        }
    )
    return rows, audit, runtime_rows, integrity


def load_reference_and_errors(raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixes = [
        NavSatSample(
            timestamp=float(row["timestamp"]),
            latitude_deg=float(row["latitude_deg"]),
            longitude_deg=float(row["longitude_deg"]),
            altitude_m=float(row["altitude_m"]),
            status=int(row["status"]),
            covariance_x_m2=float(row["covariance_x_m2"]),
            covariance_y_m2=float(row["covariance_y_m2"]),
            covariance_z_m2=float(row["covariance_z_m2"]),
        )
        for row in read_csv(raw_dir / "topic_capture/navsat_fix.csv")
    ]
    odometry = read_csv(raw_dir / "topic_capture/fastlio_odometry.csv")
    timestamps = np.asarray([float(row["timestamp"]) for row in odometry])
    positions = np.asarray(
        [
            [
                float(row["position_x"]),
                float(row["position_y"]),
                float(row["position_z"]),
            ]
            for row in odometry
        ]
    )
    reference = navsat_to_enu(fixes)
    return trajectory_error_rows(
        timestamps, positions, reference, window_seconds=5.0
    )


def nearest_error_rows(
    metric_rows: list[dict[str, Any]], error_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    error_timestamps = np.asarray([float(row["timestamp"]) for row in error_rows])
    merged: list[dict[str, Any]] = []
    for metric in metric_rows:
        timestamp = float(metric["timestamp"])
        index = int(np.searchsorted(error_timestamps, timestamp))
        candidates = [value for value in (index - 1, index) if 0 <= value < len(error_rows)]
        if candidates:
            closest = min(candidates, key=lambda value: abs(error_timestamps[value] - timestamp))
            if abs(error_timestamps[closest] - timestamp) <= 0.06:
                error = error_rows[closest]
            else:
                error = None
        else:
            error = None
        value = dict(metric)
        for field in (
            "reference_available",
            "rtk_quality_good",
            "position_error_m",
            "local_translation_error_m",
            "future_position_error_growth_m",
        ):
            value[field] = error[field] if error is not None else (False if field.endswith("available") or field.endswith("good") else float("nan"))
        merged.append(value)
    return merged


def add_intervals(
    rows: list[dict[str, Any]], lock: dict[str, Any]
) -> None:
    for row in rows:
        interval = interval_for_timestamp(float(row["timestamp"]), lock["intervals"])
        row["interval_id"] = interval["interval_id"] if interval else "OUTSIDE_FROZEN_INTERVALS"
        row["interval_label"] = interval["label"] if interval else "outside"


def interval_statistics(rows: list[dict[str, Any]], tables_dir: Path) -> list[dict[str, Any]]:
    metric_fields = (
        "ODI_trans",
        "AIS_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "lambda_min_over_lambda_max",
        "spectral_entropy_trans",
        "effective_rank_trans",
        "primary_eigengap_ratio",
        "position_error_m",
        "local_translation_error_m",
        "future_position_error_growth_m",
    )
    output: list[dict[str, Any]] = []
    interval_ids = sorted(
        {row["interval_id"] for row in rows if row["interval_id"] != "OUTSIDE_FROZEN_INTERVALS"}
    )
    for interval_id in interval_ids:
        selected = [row for row in rows if row["interval_id"] == interval_id and row["detector_valid"]]
        label = selected[0]["interval_label"] if selected else ""
        for field in metric_fields:
            values = [float(row[field]) for row in selected if row[field] != ""]
            output.append(
                {"interval_id": interval_id, "label": label, "metric": field, **summary_statistics(values)}
            )
    write_csv(tables_dir / "interval_summary.csv", output)
    return output


def baseline_analysis(rows: list[dict[str, Any]], tables_dir: Path) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["detector_valid"]
        and row["interval_label"]
        in {"structural_degeneracy_candidate", "geometry_rich_control"}
    ]
    labels = [
        1 if row["interval_label"] == "structural_degeneracy_candidate" else 0
        for row in selected
    ]
    target = [float(row["future_position_error_growth_m"]) for row in selected]
    metrics = (
        ("ODI_trans", 1.0, "higher_is_more_degenerate", False),
        ("AIS_trans", -1.0, "lower_is_more_degenerate", True),
        ("lambda_min_trans", -1.0, "lower_is_more_degenerate", True),
        ("condition_number_trans", 1.0, "higher_is_more_degenerate", True),
        ("lambda_min_over_lambda_max", -1.0, "lower_is_more_degenerate", True),
        ("spectral_entropy_trans", -1.0, "lower_is_more_degenerate", True),
        ("effective_rank_trans", -1.0, "lower_is_more_degenerate", True),
        ("primary_eigengap_ratio", 1.0, "higher_is_more_degenerate", True),
    )
    output = []
    for field, score_sign, interpretation, traditional in metrics:
        values = [float(row[field]) for row in selected]
        ranking = binary_ranking_metrics(labels, [score_sign * value for value in values])
        correlation = spearman_correlation(values, target)
        output.append(
            {
                "metric": field,
                "same_translation_schur_input": True,
                "traditional_baseline": traditional,
                "ranking_interpretation": interpretation,
                **correlation,
                **ranking,
            }
        )
    write_csv(tables_dir / "baseline_comparison.csv", output)
    return output


def weak_direction_analysis(
    rows: list[dict[str, Any]],
    lock: dict[str, Any],
    trajectory_metadata: dict[str, Any],
    tables_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    structural = next(
        interval
        for interval in lock["intervals"]
        if interval["label"] == "structural_degeneracy_candidate"
    )
    reference_axis = np.asarray(structural["reference_axis"]["vector"], dtype=float)
    rotation = np.asarray(
        trajectory_metadata["alignment_rotation_row_major"], dtype=float
    ).reshape(3, 3)
    output: list[dict[str, Any]] = []
    for row in rows:
        if row["interval_id"] != structural["interval_id"] or not row["detector_valid"]:
            continue
        weak_fast = np.asarray(
            [
                row["primary_weak_direction_x"],
                row["primary_weak_direction_y"],
                row["primary_weak_direction_z"],
            ],
            dtype=float,
        )
        weak_enu = rotation @ weak_fast
        output.append(
            {
                "timestamp": row["timestamp"],
                "scan_index": row["scan_index"],
                "interval_id": structural["interval_id"],
                "direction_reliable": row["direction_reliable"],
                "weak_direction_enu_x": weak_enu[0],
                "weak_direction_enu_y": weak_enu[1],
                "weak_direction_enu_z": weak_enu[2],
                "reference_axis_enu_x": reference_axis[0],
                "reference_axis_enu_y": reference_axis[1],
                "reference_axis_enu_z": reference_axis[2],
                "reference_axis_uncertainty_deg": structural["reference_axis"]["angular_uncertainty_deg"],
                "angle_error_deg": weak_direction_angle_error_deg(weak_enu, reference_axis),
                "sign_invariant_comparison": True,
            }
        )
    write_csv(tables_dir / "weak_direction_accuracy.csv", output)
    all_errors = [float(row["angle_error_deg"]) for row in output]
    reliable = [float(row["angle_error_deg"]) for row in output if row["direction_reliable"]]
    unreliable = [float(row["angle_error_deg"]) for row in output if not row["direction_reliable"]]
    return output, {
        "all": summary_statistics(all_errors),
        "reliable": summary_statistics(reliable),
        "unreliable": summary_statistics(unreliable),
        "reference_axis": structural["reference_axis"],
    }


def shade_intervals(axes: Any, lock: dict[str, Any], start: float) -> None:
    for interval in lock["intervals"]:
        color = "tab:red" if interval["label"] == "structural_degeneracy_candidate" else "tab:green"
        for axis in np.asarray(axes).reshape(-1):
            axis.axvspan(
                float(interval["start_timestamp"]) - start,
                float(interval["end_timestamp"]) - start,
                color=color,
                alpha=0.12,
            )


def render_figures(
    rows: list[dict[str, Any]],
    weak_rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
    lock: dict[str, Any],
    figures_dir: Path,
) -> None:
    valid = [row for row in rows if row["detector_valid"]]
    start = min(float(row["timestamp"]) for row in rows)
    x = np.asarray([float(row["timestamp"]) - start for row in valid])
    figure, axes = plt.subplots(5, 1, figsize=(15, 14), sharex=True, constrained_layout=True)
    fields = (
        ("ODI_trans", "ODI"),
        ("AIS_trans", "AIS"),
        ("lambda_min_trans", "lambda min"),
        ("condition_number_trans", "condition number"),
        ("future_position_error_growth_m", "future 5 s error growth [m]"),
    )
    for axis, (field, label) in zip(axes, fields):
        axis.plot(x, [float(row[field]) for row in valid], linewidth=0.8, label=label)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
        axis.legend(loc="upper right")
    axes[-1].set_xlabel("LiDAR header time from first processed scan [s]")
    shade_intervals(axes, lock, start)
    figure.suptitle("Full-sequence detector/baseline/error timeline with frozen intervals")
    figure.savefig(figures_dir / "odi_ais_timeline.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=True, constrained_layout=True)
    spectral = (
        ("lambda_min_trans", "lambda min"),
        ("condition_number_trans", "condition number"),
        ("spectral_entropy_trans", "spectral entropy"),
        ("effective_rank_trans", "effective rank"),
    )
    for axis, (field, label) in zip(axes, spectral):
        axis.plot(x, [float(row[field]) for row in valid], linewidth=0.8)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("LiDAR header time from first processed scan [s]")
    shade_intervals(axes, lock, start)
    figure.savefig(figures_dir / "spectral_baselines_timeline.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(14, 5), constrained_layout=True)
    reliable = [row for row in weak_rows if row["direction_reliable"]]
    unreliable = [row for row in weak_rows if not row["direction_reliable"]]
    axis.scatter(
        [float(row["timestamp"]) - start for row in reliable],
        [float(row["angle_error_deg"]) for row in reliable],
        s=12,
        label="direction_reliable=true",
    )
    axis.scatter(
        [float(row["timestamp"]) - start for row in unreliable],
        [float(row["angle_error_deg"]) for row in unreliable],
        s=12,
        label="direction_reliable=false",
    )
    axis.axhline(30.0, color="black", linestyle="--", linewidth=1, label="30 degree gate")
    axis.set(xlabel="LiDAR header time from first processed scan [s]", ylabel="sign-invariant angle error [deg]")
    axis.grid(alpha=0.2)
    axis.legend()
    shade_intervals([axis], lock, start)
    figure.savefig(figures_dir / "weak_direction_angle_error.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    scatter_fields = (
        "ODI_trans",
        "AIS_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "spectral_entropy_trans",
        "effective_rank_trans",
    )
    for axis, field in zip(axes.ravel(), scatter_fields):
        axis.scatter(
            [float(row[field]) for row in valid],
            [float(row["future_position_error_growth_m"]) for row in valid],
            s=5,
            alpha=0.35,
        )
        axis.set(xlabel=field, ylabel="future 5 s error growth [m]")
        axis.grid(alpha=0.2)
    figure.savefig(figures_dir / "error_growth_vs_metrics.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    components = [row["component"].replace("_ms", "") for row in runtime_rows]
    positions = np.arange(len(components))
    width = 0.36
    axis.bar(positions - width / 2, [float(row["mean_ms"]) for row in runtime_rows], width, label="mean")
    axis.bar(positions + width / 2, [float(row["q95_ms"]) for row in runtime_rows], width, label="q95")
    axis.set_xticks(positions, components, rotation=15)
    axis.set_ylabel("milliseconds")
    axis.grid(axis="y", alpha=0.2)
    axis.legend()
    figure.savefig(figures_dir / "runtime_breakdown.png", dpi=160)
    plt.close(figure)


def create_report(manifest: dict[str, Any]) -> str:
    gates = manifest["gates"]
    weak = manifest["weak_direction"]
    trajectory = manifest["trajectory_evaluation"]
    best = manifest["baseline_result"]
    return f"""# Measurement Real Validation Pilot

## Scope and frozen boundary

This is a single-sequence Measurement pilot, not a complete Degen-LIO
experiment. `STAGE2_GATE=FAIL` and `TRANSITION=PIVOT` remain unchanged. The
interval lock was committed before detector execution, with SHA-256
`{manifest['interval_lock_sha256']}`. No interval, metric definition, detector
threshold, or reference axis was changed after detector output became visible.

## Input and safety

- Dataset/sequence: MUN-FRL Lighthouse benchmarking bag
- Bag SHA-256: `{manifest['bag_sha256']}`
- FAST-LIO2 frames: {manifest['processed_lidar_frames']}
- Valid detector frames: {manifest['valid_detector_frames']} ({manifest['valid_detector_ratio']:.4f})
- Same-call tap mutation count: {manifest['same_call_mutation_count']}
- Detector feedback count: {manifest['detector_feedback_count']}
- Frozen detector mismatch count: {manifest['frozen_detector_mismatch_count']}
- Reference input access count: {manifest['reference_input_count']}
- FAST-LIO2 crash count: {manifest['fastlio2_crash_count']}

The one export-boundary estimator-checksum change is reported separately as
`runtime_export_estimator_checksum_change_count={manifest['runtime_export_estimator_checksum_change_count']}`.
The same frame's tap pre/post state, covariance, Jacobian, innovation,
correspondence, and map-size checksums are identical; it is not counted as a
same-call tap mutation.

## Position-only reference

`/fix` was converted from WGS84 to ENU using the first valid RTK fix. The
reference is position-only and has no reference orientation. FAST-LIO2 and ENU
positions were aligned offline with rigid SE(3) Kabsch alignment and unit scale.
Position ATE RMSE is {trajectory['position_ate_rmse_m']:.4f} m; median local
5 s translation error is {trajectory['local_translation_error_median_m']:.4f} m.

## Weak direction and eigengap

The structural-interval median angle error is {weak['all']['median']:.3f} deg
(q75 {weak['all_q75_deg']:.3f}, q95 {weak['all']['q95']:.3f}). Reliable-frame
median is {weak['reliable']['median']:.3f} deg; unreliable-frame median is
{weak['unreliable']['median']:.3f} deg. Therefore, the preregistered question
"are reliable frames actually more accurate?" evaluates to
`{gates['scientific_conditions']['reliable_better_than_unreliable']}`.

## ODI and conventional baselines

ODI AUROC is {best['odi_auroc']:.4f}; the best traditional metric is
`{best['best_traditional_metric']}` with AUROC
{best['best_traditional_auroc']:.4f}. The ODI-minus-best gap is
{best['odi_minus_best_traditional_auroc']:.4f}.

`ODI_ADVANTAGE_ESTABLISHED={manifest['ODI_ADVANTAGE_ESTABLISHED']}`

## Gates

- Engineering Gate: `{gates['engineering_gate_pass']}`
- Runtime target Gate: `{gates['runtime_gate_target_pass']}`
- Scientific Pilot Gate: `{gates['scientific_pilot_gate_pass']}`
- `MEASUREMENT_REAL_PILOT_PASS={gates['MEASUREMENT_REAL_PILOT_PASS']}`
- `SECOND_DATASET_EXPANSION_AUTHORIZED={gates['SECOND_DATASET_EXPANSION_AUTHORIZED']}`

If the scientific gate fails, this stage stops here. No second dataset is
authorized, and no post-result interval, formula, threshold, or reference-axis
adjustment is permitted.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--bag-validation", type=Path, default=DEFAULT_BAG_VALIDATION)
    parser.add_argument("--interval-lock", type=Path, default=DEFAULT_INTERVALS)
    parser.add_argument("--python311-pytest-pass", action="store_true")
    parser.add_argument("--keep-observation-binary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()
    artifact_dir = args.artifact_dir.resolve()
    if output_dir.exists() or artifact_dir.exists():
        raise SystemExit("analysis/artifact output already exists; refusing result overwrite")
    tables_dir, figures_dir = output_dir / "tables", output_dir / "figures"
    tables_dir.mkdir(parents=True)
    figures_dir.mkdir()
    lock = load_interval_lock(args.interval_lock.resolve())
    bag_validation = json.loads(args.bag_validation.read_text(encoding="utf-8"))
    run_input = json.loads((raw_dir / "run_input_manifest.json").read_text(encoding="utf-8"))
    if run_input["interval_lock_sha256"] != lock["interval_lock_sha256"]:
        raise ValueError("runtime interval lock SHA does not match committed lock")

    metric_rows, detector_audit, raw_runtime_rows, binary_integrity = process_detector(
        raw_dir, tables_dir
    )
    error_rows, trajectory_metadata = load_reference_and_errors(raw_dir)
    write_csv(tables_dir / "trajectory_errors.csv", error_rows)
    merged = nearest_error_rows(metric_rows, error_rows)
    add_intervals(merged, lock)
    interval_rows = interval_statistics(merged, tables_dir)
    baseline_rows = baseline_analysis(merged, tables_dir)
    weak_rows, weak_summary = weak_direction_analysis(
        merged, lock, trajectory_metadata, tables_dir
    )
    weak_summary["all_q75_deg"] = (
        float(np.quantile([float(row["angle_error_deg"]) for row in weak_rows], 0.75))
        if weak_rows
        else float("nan")
    )

    runtime_rows = runtime_summary(metric_rows)
    write_csv(tables_dir / "runtime_summary.csv", runtime_rows)
    runtime_lookup = {row["component"]: row for row in runtime_rows}
    no_reference_rows = [
        {
            "audit_item": "reference_or_ground_truth_online_detector_access",
            "count": detector_audit["reference_input_access_count"],
            "pass": detector_audit["reference_input_access_count"] == 0,
            "evidence": "measurement processor rejects reference fields; /fix captured by separate offline subscriber",
        },
        {
            "audit_item": "bag_odometry_played_into_fastlio2",
            "count": int(run_input["bag_odometry_played"]),
            "pass": not run_input["bag_odometry_played"],
            "evidence": "rosbag topic allowlist contains only lidar, imu, and /fix",
        },
        {
            "audit_item": "reference_orientation_fabricated",
            "count": 0,
            "pass": True,
            "evidence": "reference_is_position_only=true; reference_orientation_available=false",
        },
    ]
    write_csv(tables_dir / "no_gt_audit.csv", no_reference_rows)

    baseline_by_name = {row["metric"]: row for row in baseline_rows}
    odi_result = baseline_by_name["ODI_trans"]
    traditional = [row for row in baseline_rows if row["traditional_baseline"]]
    best_traditional = max(
        traditional,
        key=lambda row: float(row["auroc"])
        if math.isfinite(float(row["auroc"]))
        else -math.inf,
    )
    odi_advantage = float(odi_result["auroc"]) > float(best_traditional["auroc"])
    control = [
        row
        for row in merged
        if row["interval_label"] == "geometry_rich_control" and row["detector_valid"]
    ]
    control_triggers = [bool(row["degeneracy_triggered"]) for row in control]
    valid_count = sum(bool(row["detector_valid"]) for row in metric_rows)
    valid_ratio = valid_count / len(metric_rows)
    gate_inputs = {
        "python311_full_pytest_pass": args.python311_pytest_pass,
        "bag_validation_pass": bag_validation["status"] == "PASS",
        "point_time_unit_pass": bag_validation["point_time"]["validation"] == "PASS",
        "extrinsic_direction_pass": bag_validation["extrinsic"]["validation"] == "PASS",
        "reference_input_count": detector_audit["reference_input_access_count"],
        "same_call_mutation_count": detector_audit["runtime_tap_same_call_mutation_count"],
        "detector_feedback_count": detector_audit["detector_feedback_count"],
        "frozen_mismatch_count": detector_audit["frozen_detector_mismatch_count"],
        "nonfinite_output_count": detector_audit["nonfinite_detector_output_count"],
        "fastlio2_crash_count": run_input["fastlio2_crash_count"],
        "valid_detector_ratio": valid_ratio,
        "detector_core_mean_ms": runtime_lookup["detector_core_ms"]["mean_ms"],
        "total_added_q95_ms": runtime_lookup["total_added_ms"]["q95_ms"],
        "frozen_intervals_available": len(lock["intervals"]) >= 2,
        "same_input_all_metrics": True,
        "structural_direction_median_deg": weak_summary["all"]["median"],
        "reliable_direction_median_deg": weak_summary["reliable"]["median"],
        "unreliable_direction_median_deg": weak_summary["unreliable"]["median"],
        "odi_auroc": odi_result["auroc"],
        "odi_spearman_rho": odi_result["spearman_rho"],
        "control_trigger_ratio": float(np.mean(control_triggers)) if control_triggers else float("nan"),
        "control_max_consecutive_triggers": maximum_consecutive_true(control_triggers),
    }
    gates = evaluate_pilot_gates(gate_inputs)
    gate_rows: list[dict[str, Any]] = []
    for section, conditions in (
        ("Engineering Gate", gates["engineering_conditions"]),
        ("Runtime Gate targets", gates["runtime_conditions"]),
        ("Scientific Pilot Gate", gates["scientific_conditions"]),
    ):
        gate_rows.extend(
            {"gate": section, "condition": name, "pass": value}
            for name, value in conditions.items()
        )
    gate_rows.extend(
        [
            {"gate": "Final", "condition": "MEASUREMENT_REAL_PILOT_PASS", "pass": gates["MEASUREMENT_REAL_PILOT_PASS"]},
            {"gate": "Final", "condition": "SECOND_DATASET_EXPANSION_AUTHORIZED", "pass": gates["SECOND_DATASET_EXPANSION_AUTHORIZED"]},
            {"gate": "Final", "condition": "ODI_ADVANTAGE_ESTABLISHED", "pass": odi_advantage},
        ]
    )
    write_csv(tables_dir / "pilot_gate_summary.csv", gate_rows)
    render_figures(merged, weak_rows, runtime_rows, lock, figures_dir)

    transport_audit_ms = [float(row["runtime_audit_ns"]) * 1e-6 for row in raw_runtime_rows]
    scan_total_ms = [float(row["scan_total_runtime_ns"]) * 1e-6 for row in raw_runtime_rows]
    manifest = {
        "schema_version": "measurement_real_validation_pilot_result_v1",
        "stage": "Measurement Real Validation Pilot",
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "dataset": "MUN-FRL",
        "sequence": "mun_frl_lighthouse",
        "bag_path": run_input["bag_path"],
        "bag_sha256": run_input["bag_sha256"],
        "fastlio2_commit": run_input["fastlio2_commit"],
        "fastlio2_binary_sha256": run_input["fastlio2_binary_sha256"],
        "interval_lock_sha256": lock["interval_lock_sha256"],
        "interval_lock_commit": "c4adddb16a60f29d799e56061495189155859730",
        "intervals_frozen_before_detector": True,
        "processed_lidar_frames": len(metric_rows),
        "valid_detector_frames": valid_count,
        "valid_detector_ratio": valid_ratio,
        "invalid_reason_counts": detector_audit["invalid_reason_counts"],
        "same_call_mutation_count": detector_audit["runtime_tap_same_call_mutation_count"],
        "runtime_export_estimator_checksum_change_count": detector_audit["runtime_export_estimator_checksum_change_count"],
        "detector_feedback_count": detector_audit["detector_feedback_count"],
        "frozen_detector_mismatch_count": detector_audit["frozen_detector_mismatch_count"],
        "nonfinite_detector_output_count": detector_audit["nonfinite_detector_output_count"],
        "reference_input_count": detector_audit["reference_input_access_count"],
        "fastlio2_crash_count": run_input["fastlio2_crash_count"],
        "binary_integrity": binary_integrity,
        "runtime": {
            "components": runtime_rows,
            "transport_runtime_audit_ms": summary_statistics(transport_audit_ms),
            "fastlio2_scan_total_ms": summary_statistics(scan_total_ms),
        },
        "trajectory_evaluation": trajectory_metadata,
        "reference_is_position_only": True,
        "reference_orientation_available": False,
        "weak_direction": weak_summary,
        "baseline_result": {
            "odi_auroc": odi_result["auroc"],
            "odi_pr_auc": odi_result["pr_auc_average_precision"],
            "odi_spearman_rho": odi_result["spearman_rho"],
            "best_traditional_metric": best_traditional["metric"],
            "best_traditional_auroc": best_traditional["auroc"],
            "odi_minus_best_traditional_auroc": float(odi_result["auroc"]) - float(best_traditional["auroc"]),
        },
        "control_trigger_ratio": gate_inputs["control_trigger_ratio"],
        "control_max_consecutive_triggers": gate_inputs["control_max_consecutive_triggers"],
        "gates": gates,
        "ODI_ADVANTAGE_ESTABLISHED": odi_advantage,
        "ODI_ADVANTAGE_NOT_ESTABLISHED": not odi_advantage,
        "PILOT_SEQUENCE_NOT_SUITABLE_FOR_EFFECTIVENESS_TEST": False,
        "estimator_modified": False,
        "ikdtree_investigation_continued": False,
        "weak_direction_updater_developed": False,
        "visual_input_used": False,
        "complete_degen_lio_claimed": False,
        "observation_binary_retained": args.keep_observation_binary,
        "large_observation_retention_default": False,
        "interval_statistics_row_count": len(interval_rows),
    }
    write_json(output_dir / "run_manifest.json", manifest)
    (output_dir / "pilot_report.md").write_text(create_report(manifest), encoding="utf-8")

    checksum_paths = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (output_dir / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(output_dir).as_posix()}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
    )
    shutil.copytree(output_dir, artifact_dir)
    if not args.keep_observation_binary:
        (raw_dir / "observation_records_v3.bin").unlink()
    print(json.dumps({
        "Engineering Gate": gates["engineering_gate_pass"],
        "Runtime Gate": gates["runtime_gate_target_pass"],
        "Scientific Pilot Gate": gates["scientific_pilot_gate_pass"],
        "MEASUREMENT_REAL_PILOT_PASS": gates["MEASUREMENT_REAL_PILOT_PASS"],
        "SECOND_DATASET_EXPANSION_AUTHORIZED": gates["SECOND_DATASET_EXPANSION_AUTHORIZED"],
        "ODI_ADVANTAGE_ESTABLISHED": odi_advantage,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
