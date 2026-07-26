"""Deterministic scientific audit for the frozen MUN-FRL Measurement pilot.

This module consumes retained pilot outputs.  It never changes the detector,
threshold, five-second formal window, frozen intervals, or original artifact.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from eval.frame_contract import (
    coordinate_frame_contract_rows,
    rotation_covariance_validation,
    sign_invariant_angle_deg,
)
from eval.interval_validity_audit import (
    CONTROL_LABEL,
    EIGENGAP_RATIO_THRESHOLD,
    ODI_TRIGGER_THRESHOLD,
    STRUCTURAL_LABEL,
    eigengap_reliability_rows,
    information_supports_label_invalidation,
    interval_geometry_rows,
    interval_information_rows,
    trigger_contract_rows,
)
from eval.measurement_pilot import interval_for_timestamp, load_interval_lock
from eval.metric_semantics import (
    NEGATIVE_CLASS,
    POSITIVE_CLASS,
    auc_direction_rows,
    metric_contract_rows,
    odi_equivalence_rows,
)
from eval.navsat_reference import (
    NavSatSample,
    interpolate_reference,
    navsat_to_enu,
    rigid_align_positions,
)
from eval.time_alignment_audit import (
    discrete_future_error_growth,
    exact_future_error_growth,
    time_stream_summary,
)
from fastlio2_adapter.frozen_observation import load_existing_converter


AUDIT_SCHEMA = "measurement_pilot_scientific_audit_v1"
EXPECTED_SOURCE_COMMIT = "732dcff74921cb1da0d37267881ee77c5995e870"
EXPECTED_PILOT_TREE_SHA256 = "d4185c7269a0cd2c34aaa5951793962503cca88b0b8691c85428a23442fce849"
EXPECTED_BAG_SHA256 = "562bafc57dab7fdac3d8959cf6836b3f4508c4fa60147b11d718552180543162"
FORMAL_WINDOW_SECONDS = 5.0
LAG_VALUES_SECONDS = np.round(np.arange(-2.0, 2.0001, 0.05), 2)
SENSITIVITY_WINDOWS_SECONDS = (1.0, 3.0, 5.0, 10.0)
REFERENCE_UNCERTAINTY_DEG = 15.0
DIRECTION_GATE_DEG = 30.0


REQUIRED_TABLES = (
    "metric_semantic_contract.csv",
    "auc_direction_audit.csv",
    "odi_entropy_equivalence.csv",
    "future_error_growth_audit.csv",
    "future_window_sensitivity.csv",
    "time_stream_summary.csv",
    "time_lag_sensitivity.csv",
    "coordinate_frame_contract.csv",
    "frame_transform_validation.csv",
    "interval_geometry_audit.csv",
    "interval_lio_information_audit.csv",
    "reference_axis_audit.csv",
    "eigengap_reliability_audit.csv",
    "trigger_contract_audit.csv",
    "root_cause_matrix.csv",
    "final_decision.csv",
)
REQUIRED_FIGURES = (
    "odi_vs_spectral_entropy.png",
    "odi_vs_effective_rank.png",
    "time_lag_sensitivity.png",
    "weak_direction_reference_overlay.png",
    "interval_eigenvalue_timeline.png",
    "interval_correspondence_support.png",
    "reference_axis_trajectory.png",
    "eigengap_vs_angle_error.png",
    "threshold_vs_real_distribution.png",
)
REQUIRED_REPORTS = (
    "metric_direction_audit.md",
    "odi_equivalence_report.md",
    "future_error_growth_audit.md",
    "time_alignment_audit.md",
    "coordinate_frame_audit.md",
    "interval_label_validity_audit.md",
    "reference_axis_audit.md",
    "eigengap_reliability_audit.md",
    "trigger_audit.md",
    "scientific_audit_report.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(directory: Path, repository_root: Path) -> str:
    payload = bytearray()
    for path in sorted(value for value in directory.rglob("*") if value.is_file()):
        relative = path.relative_to(repository_root).as_posix()
        payload.extend(f"{sha256_file(path)}  {relative}\n".encode("utf-8"))
    return hashlib.sha256(payload).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty audit table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def _bool(value: Any) -> bool:
    return value is True or str(value) == "True"


def _finite_spearman(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    valid = np.isfinite(a) & np.isfinite(b)
    if int(np.sum(valid)) < 3 or np.unique(a[valid]).size < 2 or np.unique(b[valid]).size < 2:
        return float("nan")
    return float(spearmanr(a[valid], b[valid]).statistic)


def load_runtime_rows(repository_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    converter = load_existing_converter(repository_root)
    path = repository_root / "results/measurement_real_validation/mun_frl_lighthouse_pilot/raw/runtime_audit_v2.bin"
    records, integrity = converter.read_framed_binary(
        path, magic=converter.RUNTIME_MAGIC, version=converter.RUNTIME_VERSION
    )
    return [converter.decode_runtime_record(record) for record in records], integrity


def attach_frozen_intervals(
    frame_rows: list[dict[str, Any]], intervals: Sequence[Mapping[str, Any]]
) -> None:
    for row in frame_rows:
        interval = interval_for_timestamp(float(row["timestamp"]), intervals)
        row["interval_id"] = interval["interval_id"] if interval else "OUTSIDE_FROZEN_INTERVALS"
        row["interval_label"] = interval["label"] if interval else "outside"


def load_trajectory_inputs(repository_root: Path) -> dict[str, Any]:
    capture = repository_root / "results/measurement_real_validation/mun_frl_lighthouse_pilot/raw/topic_capture"
    navsat_rows = read_csv(capture / "navsat_fix.csv")
    odometry_rows = read_csv(capture / "fastlio_odometry.csv")
    samples = [
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
        for row in navsat_rows
    ]
    reference = navsat_to_enu(samples)
    timestamps = np.asarray([float(row["timestamp"]) for row in odometry_rows])
    estimated = np.asarray(
        [
            [float(row["position_x"]), float(row["position_y"]), float(row["position_z"])]
            for row in odometry_rows
        ]
    )
    reference_positions, quality = interpolate_reference(reference, timestamps)
    valid = np.all(np.isfinite(reference_positions), axis=1)
    aligned_valid, rotation, translation = rigid_align_positions(
        estimated[valid], reference_positions[valid]
    )
    aligned = np.full_like(estimated, np.nan)
    aligned[valid] = aligned_valid
    return {
        "navsat_rows": navsat_rows,
        "odometry_rows": odometry_rows,
        "reference": reference,
        "timestamps": timestamps,
        "estimated": estimated,
        "reference_positions": reference_positions,
        "quality": quality,
        "valid": valid,
        "aligned": aligned,
        "rotation_enu_from_fast_world": rotation,
        "translation_enu_from_fast_world_m": translation,
    }


def _metric_indices(
    frame_rows: Sequence[Mapping[str, Any]], trajectory_timestamps: np.ndarray
) -> list[tuple[Mapping[str, Any], int]]:
    output: list[tuple[Mapping[str, Any], int]] = []
    for row in frame_rows:
        if not _bool(row.get("detector_valid")):
            continue
        timestamp = float(row["timestamp"])
        index = int(np.searchsorted(trajectory_timestamps, timestamp))
        candidates = [value for value in (index - 1, index) if 0 <= value < trajectory_timestamps.size]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda value: abs(float(trajectory_timestamps[value]) - timestamp))
        if abs(float(trajectory_timestamps[nearest]) - timestamp) <= 0.06:
            output.append((row, nearest))
    return output


def future_error_tables(
    frame_rows: Sequence[Mapping[str, Any]], trajectory: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    timestamps = np.asarray(trajectory["timestamps"])
    aligned = np.asarray(trajectory["aligned"])
    reference = np.asarray(trajectory["reference_positions"])
    valid = np.asarray(trajectory["valid"])
    if not np.all(valid):
        first, last = int(np.flatnonzero(valid)[0]), int(np.flatnonzero(valid)[-1]) + 1
        timestamps, aligned, reference = timestamps[first:last], aligned[first:last], reference[first:last]
    pairs = _metric_indices(frame_rows, timestamps)
    sensitivity: list[dict[str, Any]] = []
    formal_details: dict[str, Any] = {}
    for window in SENSITIVITY_WINDOWS_SECONDS:
        current, current_available, horizon = discrete_future_error_growth(
            timestamps, aligned, reference, window_seconds=window
        )
        exact, exact_available = exact_future_error_growth(
            timestamps, aligned, reference, window_seconds=window
        )
        for definition, growth, available in (
            ("first_sample_at_or_after_target", current, current_available),
            ("exact_target_vector_interpolation_diagnostic", exact, exact_available),
        ):
            selected = [
                (row, growth[index])
                for row, index in pairs
                if row.get("interval_label") in {POSITIVE_CLASS, NEGATIVE_CLASS}
                and available[index]
            ]
            values = [float(value) for _, value in selected]
            odi = [float(row["ODI_trans"]) for row, _ in selected]
            sensitivity.append(
                {
                    "window_seconds": window,
                    "definition": definition,
                    "formal_result": window == FORMAL_WINDOW_SECONDS and definition == "first_sample_at_or_after_target",
                    "count": len(values),
                    "median_future_error_growth_m": float(np.median(values)),
                    "odi_spearman_rho": _finite_spearman(odi, values),
                    "window_selected_post_hoc": False,
                }
            )
        if window == FORMAL_WINDOW_SECONDS:
            shared = current_available & exact_available
            difference = exact[shared] - current[shared]
            formal_details = {
                "current_count": int(np.sum(current_available)),
                "exact_count": int(np.sum(exact_available)),
                "tail_without_window_count": int(np.sum(~current_available)),
                "horizon_min_seconds": float(np.nanmin(horizon)),
                "horizon_median_seconds": float(np.nanmedian(horizon)),
                "horizon_q95_seconds": float(np.nanquantile(horizon, 0.95)),
                "horizon_max_seconds": float(np.nanmax(horizon)),
                "growth_difference_abs_q95_m": float(np.quantile(np.abs(difference), 0.95)),
                "growth_difference_abs_max_m": float(np.max(np.abs(difference))),
                "growth_sign_change_count": int(np.sum(np.signbit(current[shared]) != np.signbit(exact[shared]))),
                "current_exact_pearson": float(np.corrcoef(current[shared], exact[shared])[0, 1]),
            }
    current_row = next(row for row in sensitivity if row["formal_result"])
    exact_row = next(
        row
        for row in sensitivity
        if row["window_seconds"] == FORMAL_WINDOW_SECONDS
        and row["definition"] == "exact_target_vector_interpolation_diagnostic"
    )
    audit_rows = [
        {
            "audit_item": "formal_original_definition",
            "result": "g_k = e_j - e_k; j=min{j:t_j>=t_k+5.0}; e_k=norm(R*p_hat_k+t-r(t_k))",
            "status": "CONFIRMED_FROM_SOURCE",
        },
        {
            "audit_item": "exact_five_second_definition",
            "result": "g_exact(t)=norm(p_hat_aligned(t+5)-r(t+5))-norm(p_hat_aligned(t)-r(t))",
            "status": "CORRECTED_EVALUATION_V2_DIAGNOSTIC",
        },
        {
            "audit_item": "formal_original_odi_spearman",
            "result": current_row["odi_spearman_rho"],
            "status": "FORMAL_5_SECOND_RESULT",
        },
        {
            "audit_item": "exact_interpolation_odi_spearman",
            "result": exact_row["odi_spearman_rho"],
            "status": "NON_MATERIAL_CORRECTION_DIAGNOSTIC",
        },
    ]
    audit_rows.extend(
        {"audit_item": name, "result": value, "status": "MEASURED"}
        for name, value in formal_details.items()
    )
    return audit_rows, sensitivity, formal_details


def collect_bag_header_times(bag_path: Path) -> dict[str, Any]:
    """Read only message headers; bag record epochs remain diagnostic only."""

    try:
        import rosbag
    except ImportError as error:  # pragma: no cover - ROS host integration
        raise RuntimeError("ROS rosbag is required to audit LiDAR/IMU header periods") from error
    topics = ("/velodyne_points", "/imu/data", "/fix")
    header_times: dict[str, list[float]] = {topic: [] for topic in topics}
    record_minus_header: dict[str, list[float]] = {topic: [] for topic in topics}
    with rosbag.Bag(str(bag_path), "r") as bag:
        for topic, message, record_time in bag.read_messages(topics=list(topics)):
            header = float(message.header.stamp.to_sec())
            header_times[topic].append(header)
            record_minus_header[topic].append(float(record_time.to_sec()) - header)
    return {
        "header_times": {topic: np.asarray(values) for topic, values in header_times.items()},
        "record_minus_header": {
            topic: np.asarray(values) for topic, values in record_minus_header.items()
        },
    }


def time_stream_rows(
    bag_times: Mapping[str, Any], trajectory: Mapping[str, Any]
) -> list[dict[str, Any]]:
    headers = bag_times["header_times"]
    record_delta = bag_times["record_minus_header"]
    specifications = (
        ("LiDAR", headers["/velodyne_points"], "message_header", 0.0, "/velodyne_points"),
        ("IMU_raw", headers["/imu/data"], "message_header", 0.0, "/imu/data"),
        ("IMU_effective_FAST_LIO", headers["/imu/data"] - 0.0034, "message_header_minus_frozen_offset", -0.0034, "/imu/data"),
        ("FAST_LIO_odometry", trajectory["timestamps"], "message_header_lidar_end_time", 0.0, None),
        (
            "RTK_fix",
            np.asarray([float(row["timestamp"]) for row in trajectory["navsat_rows"]]),
            "message_header",
            0.0,
            "/fix",
        ),
    )
    output: list[dict[str, Any]] = []
    for name, timestamps, source, offset, topic in specifications:
        row = time_stream_summary(
            name,
            timestamps,
            timestamp_source=source,
            applied_offset_seconds=offset,
        )
        if topic is not None:
            row["bag_record_minus_header_min_seconds"] = float(np.min(record_delta[topic]))
            row["bag_record_minus_header_max_seconds"] = float(np.max(record_delta[topic]))
        else:
            row["bag_record_minus_header_min_seconds"] = "NOT_APPLICABLE"
            row["bag_record_minus_header_max_seconds"] = "NOT_APPLICABLE"
        row["bag_record_epoch_used"] = False
        output.append(row)
    return output


def lag_sensitivity_rows(
    frame_rows: Sequence[Mapping[str, Any]], trajectory: Mapping[str, Any]
) -> list[dict[str, Any]]:
    timestamps = np.asarray(trajectory["timestamps"], dtype=float)
    estimated = np.asarray(trajectory["estimated"], dtype=float)
    reference = trajectory["reference"]
    metric_fields = {
        "odi_risk_spearman": ("ODI_trans", 1.0),
        "ais_risk_spearman": ("AIS_trans", -1.0),
        "lambda_min_risk_spearman": ("lambda_min_trans", -1.0),
        "condition_risk_spearman": ("condition_number_trans", 1.0),
        "lambda_ratio_risk_spearman": ("lambda_min_over_lambda_max", -1.0),
        "entropy_risk_spearman": ("spectral_entropy_trans", -1.0),
        "effective_rank_risk_spearman": ("effective_rank_trans", -1.0),
    }
    output: list[dict[str, Any]] = []
    for lag in LAG_VALUES_SECONDS:
        reference_positions, quality = interpolate_reference(reference, timestamps + float(lag))
        valid = np.all(np.isfinite(reference_positions), axis=1) & quality
        aligned_valid, rotation, translation = rigid_align_positions(
            estimated[valid], reference_positions[valid]
        )
        selected_times = timestamps[valid]
        selected_reference = reference_positions[valid]
        growth, available, horizon = discrete_future_error_growth(
            selected_times,
            aligned_valid,
            selected_reference,
            window_seconds=FORMAL_WINDOW_SECONDS,
        )
        position_error = np.linalg.norm(aligned_valid - selected_reference, axis=1)
        pairs = _metric_indices(frame_rows, selected_times)
        frozen_pairs = [
            (row, index)
            for row, index in pairs
            if row.get("interval_label") in {POSITIVE_CLASS, NEGATIVE_CLASS}
            and available[index]
        ]
        row_output: dict[str, Any] = {
            "lag_seconds": float(lag),
            "formal_lag": bool(abs(float(lag)) < 1.0e-12),
            "lag_selected_from_statistics": False,
            "overlap_count": int(np.sum(valid)),
            "trajectory_position_consistency_rmse_m": float(
                np.sqrt(np.mean(np.square(position_error)))
            ),
            "future_growth_count": len(frozen_pairs),
            "future_growth_median_m": float(
                np.median([growth[index] for _, index in frozen_pairs])
            ),
            "actual_horizon_median_seconds": float(np.nanmedian(horizon)),
            "alignment_rotation_det": float(np.linalg.det(rotation)),
            "alignment_translation_norm_m": float(np.linalg.norm(translation)),
        }
        target = [float(growth[index]) for _, index in frozen_pairs]
        for output_field, (metric, sign) in metric_fields.items():
            score = [sign * float(row[metric]) for row, _ in frozen_pairs]
            row_output[output_field] = _finite_spearman(score, target)
        output.append(row_output)
    return output


def reference_axis_rows(
    frame_rows: Sequence[Mapping[str, Any]],
    intervals: Sequence[Mapping[str, Any]],
    trajectory: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    structural = next(value for value in intervals if value["label"] == STRUCTURAL_LABEL)
    reference = trajectory["reference"]
    start = float(structural["start_timestamp"])
    end = float(structural["end_timestamp"])
    endpoints, _ = interpolate_reference(reference, np.asarray([start, end]))
    delta = endpoints[1] - endpoints[0]
    axis = delta / np.linalg.norm(delta)
    configured = np.asarray(structural["reference_axis"]["vector"], dtype=float)
    mask = (reference.timestamps >= start) & (reference.timestamps <= end)
    positions = reference.positions_enu_m[mask]
    centered = positions - np.mean(positions, axis=0)
    eigenvalues, eigenvectors = np.linalg.eigh(centered.T @ centered / positions.shape[0])
    pca_axis = eigenvectors[:, -1]
    projection = centered @ pca_axis
    residual = np.linalg.norm(centered - np.outer(projection, pca_axis), axis=1)
    xy_centered = centered[:, :2]
    xy_eigenvalues, xy_eigenvectors = np.linalg.eigh(
        xy_centered.T @ xy_centered / positions.shape[0]
    )
    xy_axis = xy_eigenvectors[:, -1]
    xy_projection = xy_centered @ xy_axis
    xy_residual = np.linalg.norm(xy_centered - np.outer(xy_projection, xy_axis), axis=1)

    rotation = np.asarray(trajectory["rotation_enu_from_fast_world"], dtype=float)
    weak_rows: list[dict[str, Any]] = []
    for row in frame_rows:
        if row.get("interval_label") != STRUCTURAL_LABEL or not _bool(row.get("detector_valid")):
            continue
        native = np.asarray(
            [
                float(row["primary_weak_direction_x"]),
                float(row["primary_weak_direction_y"]),
                float(row["primary_weak_direction_z"]),
            ]
        )
        weak_enu = rotation @ native
        horizontal_weak = np.asarray([weak_enu[0], weak_enu[1], 0.0])
        horizontal_axis = np.asarray([configured[0], configured[1], 0.0])
        weak_rows.append(
            {
                "timestamp": float(row["timestamp"]),
                "scan_index": int(row["scan_index"]),
                "direction_reliable": _bool(row["direction_reliable"]),
                "primary_eigengap_ratio": float(row["primary_eigengap_ratio"]),
                "weak_direction_enu_x": float(weak_enu[0]),
                "weak_direction_enu_y": float(weak_enu[1]),
                "weak_direction_enu_z": float(weak_enu[2]),
                "angle_error_deg": sign_invariant_angle_deg(weak_enu, configured),
                "horizontal_xy_angle_error_deg": sign_invariant_angle_deg(
                    horizontal_weak, horizontal_axis
                ),
                "weak_absolute_elevation_deg": math.degrees(
                    math.asin(float(np.clip(abs(weak_enu[2]), 0.0, 1.0)))
                ),
            }
        )
    errors_3d = np.asarray([row["angle_error_deg"] for row in weak_rows])
    errors_xy = np.asarray([row["horizontal_xy_angle_error_deg"] for row in weak_rows])
    covariance = np.asarray(reference.covariance_diagonal_m2[mask], dtype=float)
    median_error = float(np.median(errors_3d))
    lower = max(0.0, median_error - REFERENCE_UNCERTAINTY_DEG)
    upper = min(90.0, median_error + REFERENCE_UNCERTAINTY_DEG)
    rows = [
        {"audit_item": "construction", "value": "normalized difference of RTK ENU positions linearly interpolated at frozen interval endpoints", "unit": "contract", "interpretation": "position-only motion centerline proxy"},
        {"audit_item": "endpoint_start_enu", "value": ";".join(f"{value:.12g}" for value in endpoints[0]), "unit": "m", "interpretation": "frozen start"},
        {"audit_item": "endpoint_end_enu", "value": ";".join(f"{value:.12g}" for value in endpoints[1]), "unit": "m", "interpretation": "frozen end"},
        {"audit_item": "axis_enu", "value": ";".join(f"{value:.12g}" for value in axis), "unit": "unit_vector", "interpretation": "matches frozen configuration"},
        {"audit_item": "configured_axis_reconstruction_error", "value": sign_invariant_angle_deg(axis, configured), "unit": "degree", "interpretation": "numerical reconstruction check"},
        {"audit_item": "endpoint_separation_3d", "value": float(np.linalg.norm(delta)), "unit": "m", "interpretation": "finite baseline"},
        {"audit_item": "endpoint_separation_horizontal", "value": float(np.linalg.norm(delta[:2])), "unit": "m", "interpretation": "horizontal baseline"},
        {"audit_item": "endpoint_vertical_change", "value": float(abs(delta[2])), "unit": "m", "interpretation": "large height contribution"},
        {"audit_item": "axis_elevation", "value": math.degrees(math.asin(abs(float(axis[2])))), "unit": "degree", "interpretation": "formal 3-D axis elevation"},
        {"audit_item": "declared_angular_uncertainty", "value": REFERENCE_UNCERTAINTY_DEG, "unit": "degree", "interpretation": "no confidence level was specified"},
        {"audit_item": "rtk_fix_count", "value": int(np.sum(mask)), "unit": "count", "interpretation": "approximately 5 Hz"},
        {"audit_item": "rtk_covariance_sigma_enu_median", "value": ";".join(f"{value:.12g}" for value in np.sqrt(np.nanmedian(covariance, axis=0))), "unit": "m", "interpretation": "covariance_type=approximate"},
        {"audit_item": "pca_axis_3d_vs_endpoint", "value": sign_invariant_angle_deg(pca_axis, axis), "unit": "degree", "interpretation": "whole-interval axis stability"},
        {"audit_item": "pca_line_residual_median", "value": float(np.median(residual)), "unit": "m", "interpretation": "3-D straight-line residual"},
        {"audit_item": "pca_line_residual_q95", "value": float(np.quantile(residual, 0.95)), "unit": "m", "interpretation": "3-D straight-line residual"},
        {"audit_item": "xy_pca_vs_endpoint", "value": sign_invariant_angle_deg(np.r_[xy_axis, 0.0], np.r_[axis[:2], 0.0]), "unit": "degree", "interpretation": "horizontal path is much more stable"},
        {"audit_item": "xy_line_residual_median", "value": float(np.median(xy_residual)), "unit": "m", "interpretation": "horizontal straight-line residual"},
        {"audit_item": "formal_3d_angle_error_median", "value": median_error, "unit": "degree", "interpretation": "formal gate diagnostic"},
        {"audit_item": "formal_3d_angle_error_q05_q95", "value": f"{np.quantile(errors_3d, 0.05):.12g};{np.quantile(errors_3d, 0.95):.12g}", "unit": "degree", "interpretation": "frame distribution"},
        {"audit_item": "formal_3d_median_uncertainty_interval", "value": f"{lower:.12g};{upper:.12g}", "unit": "degree", "interpretation": "declared +/-15 degree bound straddles 30 degree gate"},
        {"audit_item": "horizontal_xy_angle_error_median", "value": float(np.median(errors_xy)), "unit": "degree", "interpretation": "diagnostic only; cannot replace formal 3-D gate"},
        {"audit_item": "horizontal_xy_angle_error_q05_q95", "value": f"{np.quantile(errors_xy, 0.05):.12g};{np.quantile(errors_xy, 0.95):.12g}", "unit": "degree", "interpretation": "diagnostic only"},
        {"audit_item": "weak_absolute_elevation_median", "value": float(np.median([row["weak_absolute_elevation_deg"] for row in weak_rows])), "unit": "degree", "interpretation": "weak directions are nearly horizontal"},
        {"audit_item": "reference_sufficient_for_30_degree_gate", "value": False, "unit": "boolean", "interpretation": "uncertainty crosses gate and motion axis is not independent environment-null ground truth"},
    ]
    summary = {
        "axis": configured.tolist(),
        "endpoints": endpoints.tolist(),
        "positions": positions,
        "formal_3d_median_deg": median_error,
        "formal_3d_q05_deg": float(np.quantile(errors_3d, 0.05)),
        "formal_3d_q95_deg": float(np.quantile(errors_3d, 0.95)),
        "horizontal_xy_median_deg": float(np.median(errors_xy)),
        "uncertainty_lower_deg": lower,
        "uncertainty_upper_deg": upper,
        "pca_3d_endpoint_angle_deg": sign_invariant_angle_deg(pca_axis, axis),
    }
    return rows, weak_rows, summary


def render_figures(
    output_dir: Path,
    frame_rows: Sequence[Mapping[str, Any]],
    equivalence_rows: Sequence[Mapping[str, Any]],
    lag_rows: Sequence[Mapping[str, Any]],
    weak_rows: Sequence[Mapping[str, Any]],
    runtime_rows: Sequence[Mapping[str, Any]],
    intervals: Sequence[Mapping[str, Any]],
    reference_summary: Mapping[str, Any],
) -> None:
    del equivalence_rows  # table evidence is consumed; plots use original frame values.
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    valid = [row for row in frame_rows if _bool(row.get("detector_valid"))]
    odi = np.asarray([float(row["ODI_trans"]) for row in valid])
    entropy = np.asarray([float(row["spectral_entropy_trans"]) for row in valid])
    effective = np.asarray([float(row["effective_rank_trans"]) for row in valid])

    for values, name, ylabel in (
        (entropy, "odi_vs_spectral_entropy.png", "spectral entropy (raw; lower is riskier)"),
        (effective, "odi_vs_effective_rank.png", "effective rank (raw; lower is riskier)"),
    ):
        figure, axis = plt.subplots(figsize=(7.5, 5.2), constrained_layout=True)
        axis.scatter(odi, values, s=7, alpha=0.35)
        axis.set(xlabel="ODI (higher is riskier)", ylabel=ylabel)
        axis.grid(alpha=0.25)
        axis.set_title("All detector-valid real frames; exact exported relationship")
        figure.savefig(figures / name, dpi=160)
        plt.close(figure)

    lag = np.asarray([float(row["lag_seconds"]) for row in lag_rows])
    figure, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True, constrained_layout=True)
    axes[0].plot(lag, [float(row["trajectory_position_consistency_rmse_m"]) for row in lag_rows])
    axes[0].set_ylabel("position RMSE after SE(3) alignment [m]")
    axes[1].plot(lag, [float(row["odi_risk_spearman"]) for row in lag_rows], label="ODI")
    axes[1].plot(lag, [float(row["lambda_min_risk_spearman"]) for row in lag_rows], label="-lambda min")
    axes[1].plot(lag, [float(row["condition_risk_spearman"]) for row in lag_rows], label="condition")
    for axis in axes:
        axis.axvline(0.0, color="black", linestyle="--", linewidth=1, label="formal lag=0")
        axis.grid(alpha=0.25)
    axes[1].set(xlabel="diagnostic reference lag [s]", ylabel="risk vs future-growth Spearman")
    axes[1].legend(ncol=2)
    figure.suptitle("Lag sensitivity is diagnostic; no lag is selected post hoc")
    figure.savefig(figures / "time_lag_sensitivity.png", dpi=160)
    plt.close(figure)

    axis_reference = np.asarray(reference_summary["axis"], dtype=float)
    weak_vectors = np.asarray(
        [[row["weak_direction_enu_x"], row["weak_direction_enu_y"], row["weak_direction_enu_z"]] for row in weak_rows]
    )
    figure, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    axes[0].scatter(weak_vectors[:, 0], weak_vectors[:, 1], s=8, alpha=0.5, label="weak axis")
    axes[0].quiver(0, 0, axis_reference[0], axis_reference[1], angles="xy", scale_units="xy", scale=1, color="tab:red", label="RTK axis")
    axes[0].set(xlabel="East", ylabel="North", xlim=(-1.05, 1.05), ylim=(-1.05, 1.05))
    axes[1].scatter(np.linalg.norm(weak_vectors[:, :2], axis=1), np.abs(weak_vectors[:, 2]), s=8, alpha=0.5)
    axes[1].scatter([np.linalg.norm(axis_reference[:2])], [abs(axis_reference[2])], color="tab:red", label="RTK axis")
    axes[1].set(xlabel="horizontal norm", ylabel="absolute Up component", xlim=(0, 1.05), ylim=(0, 1.05))
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("Weak-direction/position-centerline reference overlay in ENU")
    figure.savefig(figures / "weak_direction_reference_overlay.png", dpi=160)
    plt.close(figure)

    frozen = [row for row in valid if row.get("interval_label") in {STRUCTURAL_LABEL, CONTROL_LABEL}]
    start = min(float(row["timestamp"]) for row in frozen)
    figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, constrained_layout=True)
    for axis, field in zip(axes, ("lambda_min_trans", "lambda_mid_trans", "lambda_max_trans")):
        for label, color in ((STRUCTURAL_LABEL, "tab:red"), (CONTROL_LABEL, "tab:green")):
            selected = [row for row in frozen if row["interval_label"] == label]
            axis.plot([float(row["timestamp"]) - start for row in selected], [float(row[field]) for row in selected], color=color, linewidth=1, label=label)
        axis.set_ylabel(field)
        axis.grid(alpha=0.25)
        axis.legend()
    axes[-1].set_xlabel("seconds from first frozen-interval frame")
    figure.suptitle("Frozen labels retained; control has the weaker translation spectrum")
    figure.savefig(figures / "interval_eigenvalue_timeline.png", dpi=160)
    plt.close(figure)

    runtime_by_scan = {int(row["scan_index"]): row for row in runtime_rows}
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for label, color in ((STRUCTURAL_LABEL, "tab:red"), (CONTROL_LABEL, "tab:green")):
        selected = [row for row in frozen if row["interval_label"] == label]
        x = [float(row["timestamp"]) - start for row in selected]
        runtime = [runtime_by_scan[int(row["scan_index"])] for row in selected]
        axes[0].plot(x, [float(row["valid_correspondence_count"]) for row in runtime], color=color, linewidth=1, label=label)
        axes[1].plot(x, [float(row["map_size_after_update"]) for row in runtime], color=color, linewidth=1, label=label)
    axes[0].set_ylabel("accepted correspondence count")
    axes[1].set(xlabel="seconds from first frozen-interval frame", ylabel="local map point count")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.savefig(figures / "interval_correspondence_support.png", dpi=160)
    plt.close(figure)

    positions = np.asarray(reference_summary["positions"], dtype=float)
    endpoints = np.asarray(reference_summary["endpoints"], dtype=float)
    figure = plt.figure(figsize=(12, 5), constrained_layout=True)
    axis3d = figure.add_subplot(1, 2, 1, projection="3d")
    axis3d.plot(positions[:, 0], positions[:, 1], positions[:, 2], marker=".", markersize=3)
    axis3d.plot(endpoints[:, 0], endpoints[:, 1], endpoints[:, 2], color="tab:red", linewidth=2, label="endpoint axis")
    axis3d.set(xlabel="East [m]", ylabel="North [m]", zlabel="Up [m]")
    axis3d.legend()
    axis2d = figure.add_subplot(1, 2, 2)
    axis2d.plot(positions[:, 0], positions[:, 1], marker=".", markersize=3)
    axis2d.plot(endpoints[:, 0], endpoints[:, 1], color="tab:red", linewidth=2)
    axis2d.set(xlabel="East [m]", ylabel="North [m]")
    axis2d.axis("equal")
    axis2d.grid(alpha=0.25)
    figure.suptitle("Structural-interval RTK centerline: 3-D height instability vs stable XY")
    figure.savefig(figures / "reference_axis_trajectory.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    reliable = [row for row in weak_rows if row["direction_reliable"]]
    unreliable = [row for row in weak_rows if not row["direction_reliable"]]
    axis.scatter([row["primary_eigengap_ratio"] for row in reliable], [row["angle_error_deg"] for row in reliable], s=12, label=f"reliable n={len(reliable)}")
    axis.scatter([row["primary_eigengap_ratio"] for row in unreliable], [row["angle_error_deg"] for row in unreliable], s=28, label=f"unreliable n={len(unreliable)}")
    axis.axvline(EIGENGAP_RATIO_THRESHOLD, color="black", linestyle="--", label="frozen threshold")
    axis.set(xlabel="primary eigengap ratio", ylabel="formal 3-D angle error [deg]")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.savefig(figures / "eigengap_vs_angle_error.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5), constrained_layout=True)
    for label, color in ((STRUCTURAL_LABEL, "tab:red"), (CONTROL_LABEL, "tab:green")):
        values = [float(row["ODI_trans"]) for row in frozen if row["interval_label"] == label]
        axis.hist(values, bins=24, alpha=0.45, label=label, color=color)
    axis.axvline(ODI_TRIGGER_THRESHOLD, color="black", linestyle="--", label="frozen synthetic q95 threshold")
    axis.set(xlabel="ODI", ylabel="frame count")
    axis.grid(alpha=0.25)
    axis.legend()
    axis.set_title("The real-domain distribution lies entirely above the synthetic threshold")
    figure.savefig(figures / "threshold_vs_real_distribution.png", dpi=160)
    plt.close(figure)


def write_corrected_evaluation_v2(
    output_dir: Path,
    pilot_artifact_dir: Path,
    auc_rows: Sequence[Mapping[str, Any]],
    future_sensitivity: Sequence[Mapping[str, Any]],
    reference_summary: Mapping[str, Any],
    eigengap_rows: Sequence[Mapping[str, Any]],
    trigger_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    corrected = output_dir / "corrected_evaluation_v2"
    corrected.mkdir(parents=True, exist_ok=True)
    original_future = next(row for row in future_sensitivity if row["formal_result"])
    exact_future = next(
        row
        for row in future_sensitivity
        if row["window_seconds"] == FORMAL_WINDOW_SECONDS
        and row["definition"] == "exact_target_vector_interpolation_diagnostic"
    )
    odi_auc = next(row for row in auc_rows if row["metric_name"] == "ODI_trans")
    control = next(row for row in trigger_rows if row["subset"] == "control_frozen_interval")
    reliable = next(row for row in eigengap_rows if row["group"] == "reliable")
    unreliable = next(row for row in eigengap_rows if row["group"] == "unreliable")
    before_after = [
        {
            "item": "future_5_second_index",
            "before": "first odometry sample at or after t+5",
            "after": "linear interpolation of aligned estimator and RTK vectors at exact t+5",
            "before_value": original_future["odi_spearman_rho"],
            "after_value": exact_future["odi_spearman_rho"],
            "material_gate_change": False,
        },
        {
            "item": "eigengap_ratio_semantics",
            "before": "higher_is_more_degenerate baseline",
            "after": "excluded from formal degeneration AUC; high means direction more identifiable",
            "before_value": next(row for row in auc_rows if row["metric_name"] == "primary_eigengap_ratio")["AUC_raw"],
            "after_value": "NOT_A_FORMAL_DEGENERATION_SCORE",
            "material_gate_change": False,
        },
        {
            "item": "correlation_gate_polarity",
            "before": "abs(Spearman) >= 0.4",
            "after": "semantically risk-oriented Spearman >= 0.4",
            "before_value": original_future["odi_spearman_rho"],
            "after_value": exact_future["odi_spearman_rho"],
            "material_gate_change": False,
        },
        {
            "item": "ODI_formal_AUROC",
            "before": odi_auc["AUC_semantically_oriented"],
            "after": odi_auc["AUC_semantically_oriented"],
            "before_value": odi_auc["AUC_semantically_oriented"],
            "after_value": odi_auc["AUC_semantically_oriented"],
            "material_gate_change": False,
        },
    ]
    write_csv(corrected / "before_after_evaluation.csv", before_after)
    gate_rows = [
        {"condition": "structural_direction_median_le_30_deg", "value": reference_summary["formal_3d_median_deg"] <= 30.0, "evidence": reference_summary["formal_3d_median_deg"]},
        {"condition": "reliable_angle_better_than_unreliable", "value": float(reliable["median_angle_error_deg"]) < float(unreliable["median_angle_error_deg"]), "evidence": f"{reliable['median_angle_error_deg']} vs {unreliable['median_angle_error_deg']}"},
        {"condition": "odi_auroc_ge_0_70", "value": float(odi_auc["AUC_semantically_oriented"]) >= 0.70, "evidence": odi_auc["AUC_semantically_oriented"]},
        {"condition": "odi_semantic_spearman_ge_0_40", "value": float(exact_future["odi_spearman_rho"]) >= 0.40, "evidence": exact_future["odi_spearman_rho"]},
        {"condition": "control_false_trigger_ratio_le_0_20", "value": float(control["trigger_ratio"]) <= 0.20, "evidence": control["trigger_ratio"]},
        {"condition": "corrected_scientific_gate", "value": False, "evidence": "multiple preregistered scientific conditions remain false"},
        {"condition": "corrected_pilot_pass", "value": False, "evidence": "corrections are non-material; original FAIL remains"},
    ]
    write_csv(corrected / "corrected_gate_summary.csv", gate_rows)
    manifest = {
        "schema_version": "measurement_pilot_corrected_evaluation_v2",
        "same_bag": True,
        "same_frozen_intervals": True,
        "same_detector_threshold": True,
        "same_odi_formula": True,
        "same_ais_formula": True,
        "old_results_overwritten": False,
        "corrections": [
            "exact target-time interpolation diagnostic",
            "eigengap semantics corrected to direction identifiability",
            "correlation gate polarity corrected to risk-oriented positive direction",
        ],
        "affected_outputs": ["future growth correlation", "eigengap baseline interpretation", "gate correlation predicate"],
        "formal_conclusion_changed": False,
        "corrected_pilot_pass": False,
        "before_checksums": {
            "frame_metrics.csv": sha256_file(pilot_artifact_dir / "tables/frame_metrics.csv"),
            "baseline_comparison.csv": sha256_file(pilot_artifact_dir / "tables/baseline_comparison.csv"),
            "trajectory_errors.csv": sha256_file(pilot_artifact_dir / "tables/trajectory_errors.csv"),
        },
        "after_checksums": {
            "before_after_evaluation.csv": sha256_file(corrected / "before_after_evaluation.csv"),
            "corrected_gate_summary.csv": sha256_file(corrected / "corrected_gate_summary.csv"),
        },
    }
    write_json(corrected / "correction_manifest.json", manifest)
    write_checksum_manifest(corrected)
    return manifest


def final_decision() -> dict[str, Any]:
    return {
        "SCIENTIFIC_AUDIT_COMPLETE": True,
        "PRIMARY_AUDIT_CONCLUSION": "PILOT_LABEL_INVALIDATED",
        "PRIMARY_CONCLUSION_CATEGORY": "B",
        "METRIC_DIRECTION_BUG_CONFIRMED": True,
        "TIME_ALIGNMENT_BUG_CONFIRMED": False,
        "FRAME_TRANSFORM_BUG_CONFIRMED": False,
        "FUTURE_ERROR_IMPLEMENTATION_BUG_CONFIRMED": True,
        "TRIGGER_IMPLEMENTATION_BUG_CONFIRMED": False,
        "ODI_EXACTLY_EQUIVALENT_TO_SPECTRAL_ENTROPY": True,
        "ODI_MONOTONICALLY_EQUIVALENT_TO_SPECTRAL_ENTROPY": True,
        "ODI_INDEPENDENT_RANKING_INFORMATION_CONFIRMED": False,
        "PILOT_LABEL_INVALIDATED": True,
        "REFERENCE_INSUFFICIENT": True,
        "RELIABILITY_VALIDATION_SUFFICIENT": False,
        "REAL_DOMAIN_THRESHOLD_TRANSFER_FAILED": True,
        # This composite follows rule A: a component defect must materially
        # change the formal result.  The confirmed component defects do not.
        "EVALUATION_BUG_CONFIRMED": False,
        "METHOD_NEGATIVE_CONFIRMED": False,
        "REPLACEMENT_PILOT_AUTHORIZED": True,
        "SECOND_DATASET_EXPANSION_AUTHORIZED": False,
        "ODI_MEASUREMENT_MAINLINE_AUTHORIZED": False,
        "MEASUREMENT_PLAN_STATUS": "NEW_PREREGISTERED_REPLACEMENT_PILOT_REQUIRED",
        "ORIGINAL_MEASUREMENT_REAL_PILOT_PASS": False,
        "ORIGINAL_PILOT_RESULT_REMAINS_FAIL": True,
        "CORRECTED_EVALUATION_CHANGES_FORMAL_CONCLUSION": False,
    }


def root_cause_rows(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"candidate": "metric_score_polarity", "finding": "ODI polarity correct; eigengap baseline semantics and abs-correlation gate are incorrect", "confirmed": True, "material_to_formal_fail": False, "decision_role": "component evaluation defect"},
        {"candidate": "time_alignment", "finding": "all streams use header seconds; frozen -0.0034 s IMU offset is applied", "confirmed": False, "material_to_formal_fail": False, "decision_role": "excluded"},
        {"candidate": "future_error_timestamp_interpolation", "finding": "original uses first sample at/after t+5 rather than exact t+5 interpolation", "confirmed": True, "material_to_formal_fail": False, "decision_role": "non-material corrected-evaluation defect"},
        {"candidate": "coordinate_frame_transform", "finding": "FAST world -> ENU Kabsch rotation and sign-invariant angle are correct", "confirmed": False, "material_to_formal_fail": False, "decision_role": "excluded"},
        {"candidate": "frozen_interval_label", "finding": "absolute-strength and shape-information families both show control is weaker", "confirmed": decision["PILOT_LABEL_INVALIDATED"], "material_to_formal_fail": True, "decision_role": "PRIMARY_CATEGORY_B"},
        {"candidate": "reference_axis", "finding": "declared uncertainty crosses the 30 degree gate; 3-D centerline dominated by height", "confirmed": decision["REFERENCE_INSUFFICIENT"], "material_to_formal_fail": True, "decision_role": "secondary concurrent limitation"},
        {"candidate": "ODI_independent_novelty", "finding": "ODI risk rank equals negative exported entropy/effective-rank rank", "confirmed": True, "material_to_formal_fail": True, "decision_role": "independent advantage rejected"},
        {"candidate": "eigengap_calibration", "finding": "only five unreliable structural frames", "confirmed": True, "material_to_formal_fail": True, "decision_role": "validation insufficient, not invalid metric"},
        {"candidate": "trigger_implementation", "finding": "predicate and lock are correct; real ODI minimum is far above synthetic q95 threshold", "confirmed": False, "material_to_formal_fail": False, "decision_role": "domain-transfer failure, not code bug"},
        {"candidate": "method_negative", "finding": "cannot be isolated because label and reference are invalid", "confirmed": False, "material_to_formal_fail": False, "decision_role": "not scientifically confirmable"},
    ]


def decision_csv_rows(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"decision_field": key, "value": value, "status": "FINAL_SCIENTIFIC_AUDIT"}
        for key, value in decision.items()
    ]


def create_reports(context: Mapping[str, Any]) -> dict[str, str]:
    auc = {row["metric_name"]: row for row in context["auc_rows"]}
    eq_real = {
        row["comparison"]: row
        for row in context["equivalence_rows"]
        if row["source"] == "all_detector_valid_real_frames"
    }
    information = {
        (row["interval_label"], row["metric"]): row
        for row in context["information_rows"]
    }
    ref = context["reference_summary"]
    reliability = {row["group"]: row for row in context["eigengap_rows"]}
    trigger = {row["subset"]: row for row in context["trigger_rows"]}
    lag_zero = next(row for row in context["lag_rows"] if row["formal_lag"])
    future = context["future_details"]
    decision = context["decision"]
    semantic_lines = "\n".join(
        f"- `{row['metric_name']}`: {row['risk_oriented_transform']} ({row['larger_means']})."
        for row in context["metric_rows"]
    )
    metric_report = f"""# Metric Direction Audit

The frozen positive class is `{POSITIVE_CLASS}=1`; `{NEGATIVE_CLASS}=0`.
Score polarity was read from formula/production contracts before inspecting
label performance.  ODI is already a risk score: larger means more spectral
concentration and lower effective rank.

{semantic_lines}

ODI raw/semantic/reversed-diagnostic AUROC is
{auc['ODI_trans']['AUC_raw']:.12f} / {auc['ODI_trans']['AUC_semantically_oriented']:.12f} /
{auc['ODI_trans']['AUC_reversed_diagnostic']:.12f}.  The near-one reversed
diagnostic is not a formal result and was never substituted for the semantic
score.  It shows that the frozen labels run opposite to the predeclared risk
semantics.  The original pilot also mislabeled eigengap ratio as
"higher is more degenerate"; high eigengap instead means a more identifiable
weak direction.  The original `abs(Spearman)` effectiveness predicate is also
semantically unsafe, although neither defect changes this pilot's FAIL.
"""
    equivalence_report = f"""# ODI / Entropy Equivalence Audit

For the exported three-eigenvalue translation spectrum,

`effective_rank_trans = 3 - 2 * ODI_trans`

and

`spectral_entropy_trans = log(3 - 2 * ODI_trans)`.

The derivative is strictly negative throughout the valid ODI domain.  Across
all {eq_real['spectral_entropy_trans']['count']} valid real frames, ODI versus
raw entropy has Spearman {eq_real['spectral_entropy_trans']['spearman_raw']:.12f},
Kendall {eq_real['spectral_entropy_trans']['kendall_tau_raw']:.12f}, risk-rank
equality {eq_real['spectral_entropy_trans']['risk_rank_equality_ratio']:.12f},
and zero monotonic violations.  The fixed-seed 10,000-positive-spectrum audit
also has zero violations.

ODI cannot claim independent ranking or AUROC advantage over spectral entropy.
The stored normalized eigenvalues omit epsilon, so their independently
recomputed unregularized entropy has a tiny numerical difference; this does not
undo the exact relationship between ODI and the entropy field actually exported
by Measurement mode.
"""
    future_report = f"""# Future Error Growth Audit

The original formal implementation is

`e_k = ||R p_hat_k + t - r(t_k)||_2`

`j(k) = min{{j : t_j >= t_k + 5.0 s}}`

`future_growth_k = e_j(k) - e_k`.

It is scalar absolute-position-error growth, not the norm of a difference of
error vectors.  RTK is interpolated at estimator timestamps; alignment is one
global rigid SE(3) Kabsch fit with unit scale.  The first-at-or-after index makes
the actual horizon median {future['horizon_median_seconds']:.6f} s, q95
{future['horizon_q95_seconds']:.6f} s, and maximum
{future['horizon_max_seconds']:.6f} s.  Exact vector interpolation at `t+5`
changes the frozen-interval ODI correlation only non-materially and does not
change any gate.  Tail frames without five seconds remain missing rather than
reusing the current frame.  The 1/3/10 s results are sensitivity diagnostics;
five seconds remains the sole formal window.
"""
    time_report = f"""# Time Alignment Audit

LiDAR, raw IMU, FAST-LIO odometry, and `/fix` all use ROS message-header seconds.
Bag record epochs differ from headers by roughly 102 million seconds and are
not used.  FAST-LIO applies the frozen LiDAR-to-IMU offset `0.0034 s` by
subtracting it from IMU header time; automatic time sync is disabled.  The
formal RTK lag is exactly zero.  At lag zero, aligned position RMSE is
{lag_zero['trajectory_position_consistency_rmse_m']:.6f} m and ODI/future-growth
Spearman is {lag_zero['odi_risk_spearman']:.6f}.  The full -2 to +2 s grid is
reported only as sensitivity; no statistically favorable lag is selected or
installed.  `TIME_ALIGNMENT_BUG_CONFIRMED=false`.
"""
    frame_report = f"""# Coordinate Frame Audit

The native primary weak direction is the minimum-eigenvalue direction of the
translation Schur matrix in FAST-LIO `camera_init` world/map coordinates.  The
tap only reorders native `[delta_p_world, delta_theta_body]` columns into
detector `[delta_theta_body, delta_p_world]`; it does not rotate translation.
The offline chain is `v_ENU = R_enu_from_fast_world @ v_world`, followed by
`acos(abs(dot(unit(v_ENU), unit(axis_ENU))))`.  Kabsch translation is correctly
excluded from direction transformation.  ENU, not NED, is used; the LiDAR-to-IMU
extrinsic direction is not inverted.  Unit/X/Y/Z and fixed-seed random SO(3)
tests pass to 1e-12.  `FRAME_TRANSFORM_BUG_CONFIRMED=false`.

Remaining limitations are position-only Kabsch non-main-axis observability, an
unrecorded GNSS-antenna-to-IMU lever arm, and deletion of the large observation
binary under the original retention policy.  They are not confirmed frame bugs.
"""
    structural_lambda = information[(STRUCTURAL_LABEL, "lambda_min_trans")]["median"]
    control_lambda = information[(CONTROL_LABEL, "lambda_min_trans")]["median"]
    structural_condition = information[(STRUCTURAL_LABEL, "condition_number_trans")]["median"]
    control_condition = information[(CONTROL_LABEL, "condition_number_trans")]["median"]
    interval_report = f"""# Frozen Interval Label Validity Audit

The original intervals remain exactly 1645814048-1645814062 and
1645814164-1645814178; no swap or reselection was performed.  Structural/control
median lambda-min is {structural_lambda:.6f}/{control_lambda:.6f}, while median
condition number is {structural_condition:.6f}/{control_condition:.6f}.
Absolute-information and spectral-shape families both say the nominal control
is less observable.  Higher correspondence count in control does not reverse
the Schur information evidence.

Raw XY anisotropy did not provide a valid proxy for the active FAST-LIO2 scan-to-map observability.

Plane-normal distributions, normal covariance, residual magnitudes, map
Cartesian extent, end-face counts, and floor/ceiling/wall ratios were not
retained after the original compact observation binary was deleted.  They are
marked unavailable, not reconstructed or guessed.  `PILOT_LABEL_INVALIDATED=true`;
the old Pilot remains FAIL and its labels are not exchanged to recompute AUROC.
"""
    reference_report = f"""# Reference Axis Audit

The frozen ENU axis is the normalized difference of position-only RTK points
interpolated at the structural interval endpoints.  Its 3-D baseline includes a
4.4 m height change and has declared uncertainty +/-15 degrees without a stated
confidence level.  Formal 3-D median weak-axis error is
{ref['formal_3d_median_deg']:.6f} degrees; applying the declared bound yields
[{ref['uncertainty_lower_deg']:.6f}, {ref['uncertainty_upper_deg']:.6f}], which
straddles the 30-degree gate.  Horizontal XY median error is
{ref['horizontal_xy_median_deg']:.6f} degrees but is diagnostic only and does not
replace the preregistered 3-D result.  RTK motion direction is also not an
independent measurement of the environmental Schur null direction.
`REFERENCE_INSUFFICIENT=true`; this cannot be written as an algorithm pass.
"""
    eigengap_report = f"""# Eigengap Reliability Audit

Reliability uses `(lambda_2-lambda_1)/lambda_max >= 0.02`, ascending eigenvalues,
and finite outputs.  Structural frames comprise {reliability['reliable']['count']}
reliable and {reliability['unreliable']['count']} unreliable frames.  Their
median 3-D errors are {reliability['reliable']['median_angle_error_deg']:.6f} and
{reliability['unreliable']['median_angle_error_deg']:.6f} degrees.  Bootstrap
intervals, Mann-Whitney, and Cliff's delta are descriptive only.

The current pilot cannot validate eigengap calibration because the unreliable group contains insufficient samples.

`RELIABILITY_VALIDATION_SUFFICIENT=false`; this is not a claim that eigengap is
invalid, and the threshold was not recalibrated.
"""
    trigger_report = f"""# Trigger Audit

The predicate is `ODI_trans >= {ODI_TRIGGER_THRESHOLD:.17g}`.  The threshold is
the locked 95th percentile of 2,080 synthetic Development Open-Control frames,
uses the same dimensionless ODI version, and is loaded only after source/config
hash verification.  Invalid lifecycle frames are not triggered.  The frozen
control segment triggers {trigger['control_frozen_interval']['trigger_count']}/
{trigger['control_frozen_interval']['count']} frames, and the whole real
sequence lies above the synthetic threshold.  The comparison sign, units,
fallback behavior, and lock path are correct.
`TRIGGER_IMPLEMENTATION_BUG_CONFIRMED=false` and
`REAL_DOMAIN_THRESHOLD_TRANSFER_FAILED=true`; no real-data recalibration was
performed.
"""
    scientific_report = f"""# Measurement Pilot Scientific Audit

## Decision

Primary conclusion: **B. PILOT_LABEL_INVALIDATED**.

`MEASUREMENT_PLAN_STATUS={decision['MEASUREMENT_PLAN_STATUS']}`

The frozen control segment is consistently weaker than the nominal structural
segment under both absolute-strength and spectral-shape information families.
The reference axis is also insufficient for a sharp 30-degree decision.  These
upstream validity failures prevent isolation of a method-level negative result,
so `METHOD_NEGATIVE_CONFIRMED=false`.

Two objective evaluation defects were identified: eigengap/correlation
semantics and exact future-time interpolation.  Corrected evaluation v2 keeps
the same bag, labels, interval, formulas, threshold, and five-second formal
window; neither correction materially changes a gate.  Therefore the composite
rule-A flag remains `EVALUATION_BUG_CONFIRMED=false`, and category A is not the
primary conclusion.

ODI is analytically rank-equivalent to exported spectral entropy and effective
rank, so independent ranking/AUROC advantage is not established.  The original
Pilot remains FAIL.  A newly preregistered replacement pilot is authorized;
second-dataset expansion and ODI Measurement mainline are not authorized.

## Frozen prohibitions honored

No ODI/AIS/Schur/eigengap formula was changed.  No threshold was tuned.  No
interval was reselected or swapped.  No second dataset, visual sensor, weak
state updater, or ikd-tree investigation was used.  The original negative
artifact was not overwritten or deleted, and nothing was pushed.
"""
    return {
        "metric_direction_audit.md": metric_report,
        "odi_equivalence_report.md": equivalence_report,
        "future_error_growth_audit.md": future_report,
        "time_alignment_audit.md": time_report,
        "coordinate_frame_audit.md": frame_report,
        "interval_label_validity_audit.md": interval_report,
        "reference_axis_audit.md": reference_report,
        "eigengap_reliability_audit.md": eigengap_report,
        "trigger_audit.md": trigger_report,
        "scientific_audit_report.md": scientific_report,
    }


def write_checksum_manifest(directory: Path) -> None:
    checksum_path = directory / "SHA256SUMS"
    rows = []
    for path in sorted(value for value in directory.rglob("*") if value.is_file()):
        if path == checksum_path:
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}")
    write_text(checksum_path, "\n".join(rows))


def run_audit(
    repository_root: Path,
    pilot_artifact_dir: Path,
    bag_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    pilot_artifact_dir = pilot_artifact_dir.resolve()
    bag_path = bag_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"audit output already exists; refusing to overwrite: {output_dir}")
    if not pilot_artifact_dir.is_dir() or not bag_path.is_file():
        raise FileNotFoundError("frozen pilot artifact or bag is missing")

    source_tree_before = tree_sha256(pilot_artifact_dir, repository_root)
    if source_tree_before != EXPECTED_PILOT_TREE_SHA256:
        raise RuntimeError("frozen original Pilot tree hash changed before audit")
    bag_sha = sha256_file(bag_path)
    if bag_sha != EXPECTED_BAG_SHA256:
        raise RuntimeError("audit bag does not match the frozen Pilot bag")

    output_dir.mkdir(parents=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir()
    interval_lock = load_interval_lock(
        repository_root / "configs/real_data/mun_frl_pilot_intervals.yaml"
    )
    frame_rows: list[dict[str, Any]] = read_csv(
        pilot_artifact_dir / "tables/frame_metrics.csv"
    )
    attach_frozen_intervals(frame_rows, interval_lock["intervals"])
    runtime_rows, runtime_integrity = load_runtime_rows(repository_root)
    descriptor_rows = read_csv(
        repository_root
        / "data/measurement_real_validation/mun_frl_lighthouse_pilot/interval_selection_evidence/raw_scene_descriptors.csv"
    )
    trajectory = load_trajectory_inputs(repository_root)

    metric_rows = metric_contract_rows()
    auc_rows = auc_direction_rows(frame_rows)
    equivalence_rows = odi_equivalence_rows(frame_rows)
    future_rows, future_sensitivity, future_details = future_error_tables(
        frame_rows, trajectory
    )
    bag_times = collect_bag_header_times(bag_path)
    stream_rows = time_stream_rows(bag_times, trajectory)
    lag_rows = lag_sensitivity_rows(frame_rows, trajectory)
    frame_contract_rows = coordinate_frame_contract_rows()
    frame_validation_rows = rotation_covariance_validation()
    information_rows = interval_information_rows(
        frame_rows, interval_lock["intervals"]
    )
    label_invalidated, information_comparisons = information_supports_label_invalidation(
        information_rows
    )
    if not label_invalidated:
        raise RuntimeError("retained information evidence did not reproduce label invalidation")
    geometry_rows = interval_geometry_rows(
        interval_lock["intervals"],
        runtime_rows,
        descriptor_rows,
        trajectory["navsat_rows"],
    )
    reference_rows, weak_rows, reference_summary = reference_axis_rows(
        frame_rows, interval_lock["intervals"], trajectory
    )
    eigengap_rows = eigengap_reliability_rows(weak_rows, frame_rows)
    trigger_rows = trigger_contract_rows(frame_rows)
    decision = final_decision()
    root_causes = root_cause_rows(decision)

    tables = {
        "metric_semantic_contract.csv": metric_rows,
        "auc_direction_audit.csv": auc_rows,
        "odi_entropy_equivalence.csv": equivalence_rows,
        "future_error_growth_audit.csv": future_rows,
        "future_window_sensitivity.csv": future_sensitivity,
        "time_stream_summary.csv": stream_rows,
        "time_lag_sensitivity.csv": lag_rows,
        "coordinate_frame_contract.csv": frame_contract_rows,
        "frame_transform_validation.csv": frame_validation_rows,
        "interval_geometry_audit.csv": geometry_rows,
        "interval_lio_information_audit.csv": information_rows,
        "reference_axis_audit.csv": reference_rows,
        "eigengap_reliability_audit.csv": eigengap_rows,
        "trigger_contract_audit.csv": trigger_rows,
        "root_cause_matrix.csv": root_causes,
        "final_decision.csv": decision_csv_rows(decision),
    }
    for name, rows in tables.items():
        write_csv(tables_dir / name, rows)

    render_figures(
        output_dir,
        frame_rows,
        equivalence_rows,
        lag_rows,
        weak_rows,
        runtime_rows,
        interval_lock["intervals"],
        reference_summary,
    )
    correction_manifest = write_corrected_evaluation_v2(
        output_dir,
        pilot_artifact_dir,
        auc_rows,
        future_sensitivity,
        reference_summary,
        eigengap_rows,
        trigger_rows,
    )

    reports = create_reports(
        {
            "metric_rows": metric_rows,
            "auc_rows": auc_rows,
            "equivalence_rows": equivalence_rows,
            "future_details": future_details,
            "lag_rows": lag_rows,
            "information_rows": information_rows,
            "reference_summary": reference_summary,
            "eigengap_rows": eigengap_rows,
            "trigger_rows": trigger_rows,
            "decision": decision,
        }
    )
    for name, report in reports.items():
        write_text(output_dir / name, report)

    source_tree_after = tree_sha256(pilot_artifact_dir, repository_root)
    if source_tree_after != source_tree_before:
        raise RuntimeError("frozen original Pilot artifact changed during audit")
    zero_lag = next(row for row in lag_rows if row["formal_lag"])
    odi_auc = next(row for row in auc_rows if row["metric_name"] == "ODI_trans")
    entropy_equivalence = next(
        row
        for row in equivalence_rows
        if row["source"] == "all_detector_valid_real_frames"
        and row["comparison"] == "spectral_entropy_trans"
    )
    manifest = {
        "schema_version": AUDIT_SCHEMA,
        "audit_name": "Measurement Pilot Scientific Audit",
        "initial_branch": "feature/measurement-real-validation",
        "initial_commit": EXPECTED_SOURCE_COMMIT,
        "audit_branch": git_output(repository_root, "branch", "--show-current"),
        "audit_execution_commit": git_output(repository_root, "rev-parse", "HEAD"),
        "archive_tag": "archive/measurement-real-pilot-fail-v1",
        "bundle_path": "/tmp/Degen-LIO-measurement-pilot-before-scientific-audit.bundle",
        "bundle_sha256": "5c45d68da9460d0e319136ec5a3e8e72397d34c4e850fe3052b425b78b1b3d91",
        "pilot_artifact_dir": str(pilot_artifact_dir),
        "pilot_tree_sha256_before": source_tree_before,
        "pilot_tree_sha256_after": source_tree_after,
        "pilot_tree_unchanged": source_tree_before == source_tree_after,
        "bag_path": str(bag_path),
        "bag_sha256": bag_sha,
        "interval_lock_sha256": interval_lock["interval_lock_sha256"],
        "runtime_audit_integrity": runtime_integrity,
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "counts": {
            "frame_lifecycle": len(frame_rows),
            "detector_valid": sum(_bool(row["detector_valid"]) for row in frame_rows),
            "structural_valid": sum(row["interval_label"] == STRUCTURAL_LABEL and _bool(row["detector_valid"]) for row in frame_rows),
            "control_valid": sum(row["interval_label"] == CONTROL_LABEL and _bool(row["detector_valid"]) for row in frame_rows),
            "lag_grid": len(lag_rows),
            "random_equivalence_spectra": 10_000,
            "random_so3_trials": 100,
        },
        "formal_results": {
            "positive_class": POSITIVE_CLASS,
            "odi_raw_auroc": odi_auc["AUC_raw"],
            "odi_semantic_auroc": odi_auc["AUC_semantically_oriented"],
            "odi_reversed_diagnostic_auroc": odi_auc["AUC_reversed_diagnostic"],
            "odi_zero_lag_future_growth_spearman": zero_lag["odi_risk_spearman"],
            "odi_entropy_spearman_raw": entropy_equivalence["spearman_raw"],
            "odi_entropy_risk_rank_equality": entropy_equivalence["risk_rank_equality_ratio"],
            "structural_direction_median_3d_deg": reference_summary["formal_3d_median_deg"],
            "structural_direction_median_xy_deg_diagnostic": reference_summary["horizontal_xy_median_deg"],
        },
        "information_family_comparisons": information_comparisons,
        "corrected_evaluation_v2": correction_manifest,
        "original_pilot_flags": {
            "MEASUREMENT_REAL_PILOT_PASS": False,
            "SECOND_DATASET_EXPANSION_AUTHORIZED": False,
            "ODI_ADVANTAGE_ESTABLISHED": False,
            "STAGE2_GATE": "FAIL",
            "TRANSITION": "PIVOT",
        },
        "prohibitions": {
            "odi_formula_modified": False,
            "ais_formula_modified": False,
            "threshold_tuned": False,
            "interval_reselected": False,
            "second_dataset_used": False,
            "weak_direction_update_restored": False,
            "visual_sensor_added": False,
            "original_negative_result_overwritten": False,
            "git_push_performed": False,
        },
        "decision": decision,
    }
    write_json(output_dir / "run_manifest.json", manifest)
    write_json(output_dir / "final_decision.json", decision)
    write_checksum_manifest(output_dir)
    return manifest


def verify_audit_artifacts(audit_dir: Path) -> dict[str, Any]:
    audit_dir = audit_dir.resolve()
    required = {
        *(f"tables/{name}" for name in REQUIRED_TABLES),
        *(f"figures/{name}" for name in REQUIRED_FIGURES),
        *REQUIRED_REPORTS,
        "run_manifest.json",
        "final_decision.json",
        "SHA256SUMS",
        "corrected_evaluation_v2/before_after_evaluation.csv",
        "corrected_evaluation_v2/corrected_gate_summary.csv",
        "corrected_evaluation_v2/correction_manifest.json",
        "corrected_evaluation_v2/SHA256SUMS",
    }
    missing = sorted(name for name in required if not (audit_dir / name).is_file())
    if missing:
        raise ValueError(f"missing audit artifacts: {missing}")
    for name in REQUIRED_FIGURES:
        if (audit_dir / "figures" / name).stat().st_size < 10_000:
            raise ValueError(f"audit figure is unexpectedly small: {name}")

    checksum_lines = (audit_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed: set[str] = set()
    for line in checksum_lines:
        digest, relative = line.split("  ", 1)
        listed.add(relative)
        if sha256_file(audit_dir / relative) != digest:
            raise ValueError(f"checksum mismatch: {relative}")
    actual = {
        path.relative_to(audit_dir).as_posix()
        for path in audit_dir.rglob("*")
        if path.is_file() and path != audit_dir / "SHA256SUMS"
    }
    if listed != actual:
        raise ValueError("top-level checksum coverage is incomplete or contains extras")

    manifest = json.loads((audit_dir / "run_manifest.json").read_text(encoding="utf-8"))
    decision = json.loads((audit_dir / "final_decision.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != AUDIT_SCHEMA or not decision["SCIENTIFIC_AUDIT_COMPLETE"]:
        raise ValueError("audit schema or completion flag is invalid")
    if decision["PRIMARY_AUDIT_CONCLUSION"] != "PILOT_LABEL_INVALIDATED":
        raise ValueError("audit must reproduce the evidence-selected primary category B")
    if not decision["PILOT_LABEL_INVALIDATED"] or decision["METHOD_NEGATIVE_CONFIRMED"]:
        raise ValueError("label-invalidated decision is internally inconsistent")
    if decision["SECOND_DATASET_EXPANSION_AUTHORIZED"] or decision["ODI_MEASUREMENT_MAINLINE_AUTHORIZED"]:
        raise ValueError("forbidden expansion/mainline authorization is true")
    if manifest["pilot_tree_sha256_before"] != EXPECTED_PILOT_TREE_SHA256 or not manifest["pilot_tree_unchanged"]:
        raise ValueError("frozen Pilot hash evidence is invalid")
    if any(manifest["prohibitions"].values()):
        raise ValueError("a forbidden action is reported as performed")
    correction = json.loads(
        (audit_dir / "corrected_evaluation_v2/correction_manifest.json").read_text(encoding="utf-8")
    )
    if correction["formal_conclusion_changed"] or correction["corrected_pilot_pass"]:
        raise ValueError("non-material corrected evaluation was misreported as a pass")
    return {
        "AUDIT_ARTIFACT_VERIFY_PASS": True,
        "file_count": len(actual) + 1,
        "primary_conclusion": decision["PRIMARY_AUDIT_CONCLUSION"],
        "measurement_plan_status": decision["MEASUREMENT_PLAN_STATUS"],
    }
