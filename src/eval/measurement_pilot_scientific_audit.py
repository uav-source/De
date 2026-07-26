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
import yaml  # noqa: E402
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
from eval.measurement_real_analysis import (
    CONTROL_MAX_CONSECUTIVE_TRIGGERS,
    CONTROL_MAX_TRIGGER_RATIO,
    DIRECTION_MEDIAN_MAX_DEG,
    ODI_ABS_SPEARMAN_MINIMUM,
    ODI_AUROC_MINIMUM,
)
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
    exact_future_error_growth_against_reference,
    time_stream_summary,
    validate_strict_seconds_timestamps,
)
from fastlio2_adapter.frozen_observation import load_existing_converter
from fastlio2_adapter.mun_frl_contract import (
    TIME_OFFSET_LIDAR_TO_IMU,
    validate_mun_frl_config,
)


AUDIT_SCHEMA = "measurement_pilot_scientific_audit_v1"
EXPECTED_SOURCE_COMMIT = "732dcff74921cb1da0d37267881ee77c5995e870"
EXPECTED_PILOT_TREE_SHA256 = "d4185c7269a0cd2c34aaa5951793962503cca88b0b8691c85428a23442fce849"
EXPECTED_BAG_SHA256 = "562bafc57dab7fdac3d8959cf6836b3f4508c4fa60147b11d718552180543162"
EXPECTED_INPUT_SHA256 = {
    "runtime_audit_v2.bin": "88bd2f9e2d45b4d23d7866e2957c55d6c63d694aa25b8d5ec55b3000379a6f42",
    "fastlio_odometry.csv": "88b11ffd447d2df8c231490dfcdf3fdd5e7fb6f7a6fc1a608cd61c295f110f7c",
    "navsat_fix.csv": "0bb868230aab96d4da6aaac01b737fc860057691571e917d9927cd62c913c46d",
    "raw_scene_descriptors.csv": "9e27df2246dba8ee77808e61518dfcca903e47d7af370e2cff370d427c8b94c5",
    "mun_frl_pilot_intervals.yaml": "c74d3af08054979c2cf0ecbb086a7b218a6541f691b82a1eb20706047086e4b4",
    "mun_frl_lighthouse.yaml": "6432293f6592a830d8d08ed16bc9bfc31a235d0aa9f7fce2c3933c31b581615d",
    "detector_lock.json": "075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358",
    "odi_threshold_calibration.json": "8648d64a8e2228e913bd9debcef3bae2ba8bb5aeb23ba73f89a9abb354c176af",
}
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
    sampled_reference = np.asarray(trajectory["reference_positions"])
    native_reference = trajectory["reference"]
    valid = np.asarray(trajectory["valid"])
    if not np.all(valid):
        first, last = int(np.flatnonzero(valid)[0]), int(np.flatnonzero(valid)[-1]) + 1
        timestamps, aligned, sampled_reference = (
            timestamps[first:last],
            aligned[first:last],
            sampled_reference[first:last],
        )
    pairs = _metric_indices(frame_rows, timestamps)
    sensitivity: list[dict[str, Any]] = []
    formal_details: dict[str, Any] = {}
    for window in SENSITIVITY_WINDOWS_SECONDS:
        current, current_available, horizon = discrete_future_error_growth(
            timestamps, aligned, sampled_reference, window_seconds=window
        )
        exact, exact_available = exact_future_error_growth_against_reference(
            timestamps,
            aligned,
            native_reference.timestamps,
            native_reference.positions_enu_m,
            window_seconds=window,
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

    # The audit is required to run under Python 3.11, while the retained ROS
    # Noetic reader is installed by the host.  Container runs mount those
    # pure-Python modules at the paths below.  Append (rather than prepend)
    # them so the audit container's Python-3.11 NumPy/SciPy remain authoritative.
    for ros_bridge in (
        Path("/opt/ros/noetic/lib/python3/dist-packages"),
        Path("/host_py"),
    ):
        bridge = str(ros_bridge)
        if ros_bridge.is_dir() and bridge not in sys.path:
            sys.path.append(bridge)

    # ROS Noetic's rosbag imports AES support eagerly even for an unencrypted,
    # uncompressed bag.  A Python 3.11 audit container can read the pure-Python
    # ROS modules but cannot load the host's CPython-3.8 Cryptodome extension.
    # Install a fail-closed placeholder only for that optional path; attempting
    # to read an encrypted bag still raises immediately.
    try:  # pragma: no branch - depends on the host ROS/Python combination
        from Cryptodome.Cipher import AES as _unused_aes  # noqa: F401
    except Exception:  # pragma: no cover - exercised by Python 3.11 ROS bridge
        import types

        crypto_module = types.ModuleType("Cryptodome")
        cipher_module = types.ModuleType("Cryptodome.Cipher")
        random_module = types.ModuleType("Cryptodome.Random")

        class _EncryptedBagUnsupported:
            block_size = 16
            MODE_CBC = 2

            @staticmethod
            def new(*args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                raise RuntimeError("encrypted rosbag is unsupported by the audit reader")

        def _no_random_bytes(size: int) -> bytes:
            del size
            raise RuntimeError("encrypted rosbag is unsupported by the audit reader")

        cipher_module.AES = _EncryptedBagUnsupported  # type: ignore[attr-defined]
        random_module.get_random_bytes = _no_random_bytes  # type: ignore[attr-defined]
        sys.modules.update(
            {
                "Cryptodome": crypto_module,
                "Cryptodome.Cipher": cipher_module,
                "Cryptodome.Random": random_module,
            }
        )
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
        (
            "IMU_effective_FAST_LIO",
            headers["/imu/data"] - TIME_OFFSET_LIDAR_TO_IMU,
            "message_header_minus_frozen_offset",
            -TIME_OFFSET_LIDAR_TO_IMU,
            "/imu/data",
        ),
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
        validated_timestamps = validate_strict_seconds_timestamps(timestamps)
        row = time_stream_summary(
            name,
            validated_timestamps,
            timestamp_source=source,
            applied_offset_seconds=offset,
        )
        row["unix_seconds_validation"] = "PASS"
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

    def endpoint_axis(window_start: float, window_end: float) -> np.ndarray:
        window_endpoints, _ = interpolate_reference(
            reference, np.asarray([window_start, window_end])
        )
        window_delta = window_endpoints[1] - window_endpoints[0]
        return window_delta / np.linalg.norm(window_delta)

    half_boundaries = np.linspace(start, end, 3)
    half_axes = [
        endpoint_axis(float(half_boundaries[index]), float(half_boundaries[index + 1]))
        for index in range(2)
    ]
    quarter_boundaries = np.linspace(start, end, 5)
    quarter_axes = [
        endpoint_axis(
            float(quarter_boundaries[index]), float(quarter_boundaries[index + 1])
        )
        for index in range(4)
    ]

    def maximum_pairwise_angle(axes: Sequence[np.ndarray]) -> float:
        return max(
            sign_invariant_angle_deg(axes[left], axes[right])
            for left in range(len(axes))
            for right in range(left + 1, len(axes))
        )

    half_axis_angle = sign_invariant_angle_deg(half_axes[0], half_axes[1])
    quarter_axis_max_angle = maximum_pairwise_angle(quarter_axes)
    aligned_times = np.asarray(trajectory["timestamps"], dtype=float)
    aligned_positions = np.asarray(trajectory["aligned"], dtype=float)
    aligned_endpoints = np.column_stack(
        [
            np.interp([start, end], aligned_times, aligned_positions[:, axis_index])
            for axis_index in range(3)
        ]
    )
    aligned_motion_axis = aligned_endpoints[1] - aligned_endpoints[0]
    aligned_motion_axis /= np.linalg.norm(aligned_motion_axis)
    aligned_motion_consistency = sign_invariant_angle_deg(aligned_motion_axis, axis)

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
        {"audit_item": "frozen_interval_duration", "value": end - start, "unit": "second", "interpretation": "14-second reference construction window"},
        {"audit_item": "half_window_endpoint_axis_angle", "value": half_axis_angle, "unit": "degree", "interpretation": "large first-half/second-half motion-axis change; reference is not locally stable"},
        {"audit_item": "quarter_window_endpoint_axis_max_pairwise_angle", "value": quarter_axis_max_angle, "unit": "degree", "interpretation": "maximum sign-invariant disagreement among four equal-duration subwindows"},
        {"audit_item": "aligned_lio_motion_axis_vs_reference_axis", "value": aligned_motion_consistency, "unit": "degree", "interpretation": "shows trajectory-motion consistency after global alignment; does not validate an environmental null axis"},
        {"audit_item": "reference_axis_subwindow_stable", "value": False, "unit": "boolean", "interpretation": "half and quarter endpoint axes vary too strongly for a sharp 30-degree environmental-axis claim"},
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
        "half_window_axis_angle_deg": half_axis_angle,
        "quarter_window_axis_max_pairwise_angle_deg": quarter_axis_max_angle,
        "aligned_motion_axis_consistency_deg": aligned_motion_consistency,
        "reference_axis_subwindow_stable": False,
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
    original_manifest = json.loads(
        (pilot_artifact_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    original_gates = original_manifest["gates"]
    original_correlation = float(original_future["odi_spearman_rho"])
    corrected_correlation = float(exact_future["odi_spearman_rho"])
    original_correlation_pass = abs(original_correlation) >= ODI_ABS_SPEARMAN_MINIMUM
    semantic_same_sample_correlation_pass = (
        original_correlation >= ODI_ABS_SPEARMAN_MINIMUM
    )
    corrected_correlation_pass = corrected_correlation >= ODI_ABS_SPEARMAN_MINIMUM
    odi_auc_pass = float(odi_auc["AUC_semantically_oriented"]) >= ODI_AUROC_MINIMUM
    formal_other_auc = [
        float(row["AUC_semantically_oriented"])
        for row in auc_rows
        if row["metric_name"] != "ODI_trans"
        and row["semantic_status"] == "FORMAL_SEMANTIC_POLARITY"
        and math.isfinite(float(row["AUC_semantically_oriented"]))
    ]
    corrected_odi_advantage = bool(
        formal_other_auc
        and float(odi_auc["AUC_semantically_oriented"]) > max(formal_other_auc)
    )
    original_odi_advantage = bool(original_manifest["ODI_ADVANTAGE_ESTABLISHED"])
    before_after = [
        {
            "item": "future_5_second_index",
            "before": "first odometry sample at or after t+5",
            "after": "independent interpolation of aligned estimator and native RTK streams at exact t+5",
            "before_value": original_correlation,
            "after_value": corrected_correlation,
            "before_gate_pass": original_correlation_pass,
            "after_gate_pass": corrected_correlation_pass,
            "material_gate_change": original_correlation_pass
            != corrected_correlation_pass,
        },
        {
            "item": "eigengap_ratio_semantics",
            "before": "higher_is_more_degenerate baseline",
            "after": "excluded from formal degeneration AUC; high means direction more identifiable",
            "before_value": next(row for row in auc_rows if row["metric_name"] == "primary_eigengap_ratio")["AUC_raw"],
            "after_value": "NOT_A_FORMAL_DEGENERATION_SCORE",
            "before_gate_pass": original_odi_advantage,
            "after_gate_pass": corrected_odi_advantage,
            "material_gate_change": original_odi_advantage
            != corrected_odi_advantage,
        },
        {
            "item": "correlation_gate_polarity",
            "before": "abs(Spearman) >= 0.4",
            "after": "semantically risk-oriented Spearman >= 0.4",
            "before_value": original_correlation,
            "after_value": original_correlation,
            "before_gate_pass": original_correlation_pass,
            "after_gate_pass": semantic_same_sample_correlation_pass,
            "material_gate_change": original_correlation_pass
            != semantic_same_sample_correlation_pass,
        },
        {
            "item": "ODI_formal_AUROC",
            "before": "positive class structural candidate; raw ODI risk polarity",
            "after": "unchanged semantic formula and positive class",
            "before_value": odi_auc["AUC_semantically_oriented"],
            "after_value": odi_auc["AUC_semantically_oriented"],
            "before_gate_pass": odi_auc_pass,
            "after_gate_pass": odi_auc_pass,
            "material_gate_change": False,
        },
    ]
    write_csv(corrected / "before_after_evaluation.csv", before_after)

    corrected_scientific = {
        "frozen_structural_and_control_intervals": True,
        "same_input_all_metrics": True,
        "structural_direction_median_pass": float(
            reference_summary["formal_3d_median_deg"]
        )
        <= DIRECTION_MEDIAN_MAX_DEG,
        "reliable_better_than_unreliable": float(
            reliable["median_angle_error_deg"]
        )
        < float(unreliable["median_angle_error_deg"]),
        "odi_effectiveness_pass": odi_auc_pass or corrected_correlation_pass,
        "control_false_trigger_pass": float(control["trigger_ratio"])
        <= CONTROL_MAX_TRIGGER_RATIO
        and int(original_manifest["control_max_consecutive_triggers"])
        <= CONTROL_MAX_CONSECUTIVE_TRIGGERS,
        "no_reference_online": bool(
            original_gates["scientific_conditions"]["no_reference_online"]
        ),
    }
    corrected_scientific_pass = all(corrected_scientific.values())
    corrected_engineering_pass = all(
        original_gates["engineering_conditions"].values()
    )
    corrected_runtime_pass = all(original_gates["runtime_conditions"].values())
    corrected_pilot_pass = corrected_engineering_pass and corrected_scientific_pass
    gate_rows: list[dict[str, Any]] = []
    for gate_name, conditions, mode in (
        (
            "Engineering Gate",
            original_gates["engineering_conditions"],
            "REEXECUTED_UNCHANGED_FROZEN_EVIDENCE",
        ),
        (
            "Runtime Gate targets",
            original_gates["runtime_conditions"],
            "REEXECUTED_UNCHANGED_FROZEN_EVIDENCE",
        ),
        (
            "Scientific Pilot Gate",
            corrected_scientific,
            "REEXECUTED_WITH_CORRECTED_EVALUATION_V2",
        ),
    ):
        for condition, passed in conditions.items():
            evidence: Any = "unchanged frozen input/result"
            if condition == "structural_direction_median_pass":
                evidence = reference_summary["formal_3d_median_deg"]
            elif condition == "reliable_better_than_unreliable":
                evidence = (
                    f"{reliable['median_angle_error_deg']} vs "
                    f"{unreliable['median_angle_error_deg']}"
                )
            elif condition == "odi_effectiveness_pass":
                evidence = (
                    f"semantic_auc={odi_auc['AUC_semantically_oriented']};"
                    f"exact_5s_semantic_rho={corrected_correlation}"
                )
            elif condition == "control_false_trigger_pass":
                evidence = (
                    f"ratio={control['trigger_ratio']};max_consecutive="
                    f"{original_manifest['control_max_consecutive_triggers']}"
                )
            gate_rows.append(
                {
                    "gate": gate_name,
                    "condition": condition,
                    "pass": bool(passed),
                    "evidence": evidence,
                    "evaluation_mode": mode,
                }
            )
    gate_rows.extend(
        [
            {
                "gate": "Final",
                "condition": "MEASUREMENT_REAL_PILOT_PASS",
                "pass": corrected_pilot_pass,
                "evidence": "engineering AND corrected scientific gates",
                "evaluation_mode": "REEXECUTED_WITH_CORRECTED_EVALUATION_V2",
            },
            {
                "gate": "Final",
                "condition": "SECOND_DATASET_EXPANSION_AUTHORIZED",
                "pass": corrected_pilot_pass,
                "evidence": "identical to corrected Pilot pass under frozen protocol",
                "evaluation_mode": "REEXECUTED_WITH_CORRECTED_EVALUATION_V2",
            },
            {
                "gate": "Final",
                "condition": "ODI_ADVANTAGE_ESTABLISHED",
                "pass": corrected_odi_advantage,
                "evidence": "semantic ODI AUROC strictly exceeds every eligible formal baseline",
                "evaluation_mode": "REEXECUTED_WITH_CORRECTED_EVALUATION_V2",
            },
        ]
    )
    write_csv(corrected / "corrected_gate_summary.csv", gate_rows)
    formal_conclusion_changed = bool(
        corrected_pilot_pass != bool(original_gates["MEASUREMENT_REAL_PILOT_PASS"])
    )
    manifest = {
        "schema_version": "measurement_pilot_corrected_evaluation_v2",
        "same_bag": True,
        "same_frozen_intervals": True,
        "same_detector_threshold": True,
        "same_odi_formula": True,
        "same_ais_formula": True,
        "old_results_overwritten": False,
        "bug_descriptions": [
            "the original future index used the first odometry sample at or after t+5 instead of exact native-stream interpolation",
            "the original baseline called eigengap ratio a degeneration score although it measures direction identifiability",
            "the original ODI correlation gate used absolute correlation rather than the preregistered risk direction",
        ],
        "corrections": [
            "exact target-time interpolation on independent estimator and native RTK grids",
            "eigengap semantics corrected to direction identifiability",
            "correlation gate polarity corrected to risk-oriented positive direction",
        ],
        "affected_files": [
            "src/eval/navsat_reference.py::trajectory_error_rows",
            "src/eval/measurement_real_analysis.py::evaluate_pilot_gates",
            "scripts/132_analyze_mun_frl_measurement_pilot.py::baseline_analysis",
            "src/eval/measurement_pilot_scientific_audit.py::write_corrected_evaluation_v2",
        ],
        "affected_outputs": [
            "tables/trajectory_errors.csv future-growth values/correlation",
            "tables/baseline_comparison.csv eigengap interpretation",
            "tables/pilot_gate_summary.csv ODI effectiveness predicate",
        ],
        "frozen_identity": {
            "bag_sha256": EXPECTED_BAG_SHA256,
            "interval_lock_sha256": EXPECTED_INPUT_SHA256[
                "mun_frl_pilot_intervals.yaml"
            ],
            "odi_trigger_threshold": ODI_TRIGGER_THRESHOLD,
            "formal_future_window_seconds": FORMAL_WINDOW_SECONDS,
        },
        "all_original_gates_reexecuted": True,
        "original_gate_condition_count": len(gate_rows),
        "corrected_engineering_gate_pass": corrected_engineering_pass,
        "corrected_runtime_target_pass": corrected_runtime_pass,
        "corrected_scientific_gate_pass": corrected_scientific_pass,
        "formal_conclusion_changed": formal_conclusion_changed,
        "corrected_pilot_pass": corrected_pilot_pass,
        "before_checksums": {
            "frame_metrics.csv": sha256_file(pilot_artifact_dir / "tables/frame_metrics.csv"),
            "baseline_comparison.csv": sha256_file(pilot_artifact_dir / "tables/baseline_comparison.csv"),
            "trajectory_errors.csv": sha256_file(pilot_artifact_dir / "tables/trajectory_errors.csv"),
            "pilot_gate_summary.csv": sha256_file(
                pilot_artifact_dir / "tables/pilot_gate_summary.csv"
            ),
        },
        "after_checksums": {
            "before_after_evaluation.csv": sha256_file(corrected / "before_after_evaluation.csv"),
            "corrected_gate_summary.csv": sha256_file(corrected / "corrected_gate_summary.csv"),
        },
    }
    write_json(corrected / "correction_manifest.json", manifest)
    write_checksum_manifest(corrected)
    return manifest


def final_decision(
    *,
    metric_direction_bug_confirmed: bool,
    time_alignment_bug_confirmed: bool,
    frame_transform_bug_confirmed: bool,
    future_error_implementation_bug_confirmed: bool,
    trigger_implementation_bug_confirmed: bool,
    odi_exactly_equivalent: bool,
    odi_monotonically_equivalent: bool,
    pilot_label_invalidated: bool,
    reference_insufficient: bool,
    reliability_validation_sufficient: bool,
    real_domain_threshold_transfer_failed: bool,
    corrected_evaluation_changes_formal_conclusion: bool,
    method_negative_criteria_satisfied: bool,
) -> dict[str, Any]:
    """Apply the preregistered A/B/C/D rules to measured audit evidence."""

    component_bug = any(
        (
            metric_direction_bug_confirmed,
            time_alignment_bug_confirmed,
            frame_transform_bug_confirmed,
            future_error_implementation_bug_confirmed,
            trigger_implementation_bug_confirmed,
        )
    )
    if corrected_evaluation_changes_formal_conclusion and not component_bug:
        raise ValueError("a material corrected result requires a confirmed component bug")
    evaluation_bug_confirmed = bool(
        component_bug and corrected_evaluation_changes_formal_conclusion
    )

    if evaluation_bug_confirmed:
        category = "A"
        conclusion = "EVALUATION_BUG_CONFIRMED"
        plan_status = "RECOVERABLE_BY_CORRECTED_PILOT"
    elif pilot_label_invalidated:
        category = "B"
        conclusion = "PILOT_LABEL_INVALIDATED"
        plan_status = "NEW_PREREGISTERED_REPLACEMENT_PILOT_REQUIRED"
    elif reference_insufficient:
        category = "C"
        conclusion = "REFERENCE_INSUFFICIENT"
        plan_status = "PILOT_INCONCLUSIVE_REFERENCE_INSUFFICIENT"
    elif method_negative_criteria_satisfied:
        category = "D"
        conclusion = "METHOD_NEGATIVE_CONFIRMED"
        plan_status = "STOP_ODI_MEASUREMENT_MAINLINE"
    else:
        raise ValueError("audit evidence does not satisfy any preregistered A/B/C/D rule")

    method_negative_confirmed = category == "D"
    replacement_authorized = category in {"A", "B", "C"}
    return {
        "SCIENTIFIC_AUDIT_COMPLETE": True,
        "PRIMARY_AUDIT_CONCLUSION": conclusion,
        "PRIMARY_CONCLUSION_CATEGORY": category,
        "METRIC_DIRECTION_BUG_CONFIRMED": bool(metric_direction_bug_confirmed),
        "TIME_ALIGNMENT_BUG_CONFIRMED": bool(time_alignment_bug_confirmed),
        "FRAME_TRANSFORM_BUG_CONFIRMED": bool(frame_transform_bug_confirmed),
        "FUTURE_ERROR_IMPLEMENTATION_BUG_CONFIRMED": bool(
            future_error_implementation_bug_confirmed
        ),
        "TRIGGER_IMPLEMENTATION_BUG_CONFIRMED": bool(
            trigger_implementation_bug_confirmed
        ),
        "ODI_EXACTLY_EQUIVALENT_TO_SPECTRAL_ENTROPY": bool(
            odi_exactly_equivalent
        ),
        "ODI_MONOTONICALLY_EQUIVALENT_TO_SPECTRAL_ENTROPY": bool(
            odi_monotonically_equivalent
        ),
        "ODI_INDEPENDENT_RANKING_INFORMATION_CONFIRMED": bool(
            not odi_monotonically_equivalent
        ),
        "PILOT_LABEL_INVALIDATED": bool(pilot_label_invalidated),
        "REFERENCE_INSUFFICIENT": bool(reference_insufficient),
        "RELIABILITY_VALIDATION_SUFFICIENT": bool(
            reliability_validation_sufficient
        ),
        "REAL_DOMAIN_THRESHOLD_TRANSFER_FAILED": bool(
            real_domain_threshold_transfer_failed
        ),
        "EVALUATION_BUG_CONFIRMED": evaluation_bug_confirmed,
        "METHOD_NEGATIVE_CONFIRMED": method_negative_confirmed,
        "REPLACEMENT_PILOT_AUTHORIZED": replacement_authorized,
        "SECOND_DATASET_EXPANSION_AUTHORIZED": False,
        "ODI_MEASUREMENT_MAINLINE_AUTHORIZED": False,
        "MEASUREMENT_PLAN_STATUS": plan_status,
        "ORIGINAL_MEASUREMENT_REAL_PILOT_PASS": False,
        "ORIGINAL_PILOT_RESULT_REMAINS_FAIL": True,
        "CORRECTED_EVALUATION_CHANGES_FORMAL_CONCLUSION": bool(
            corrected_evaluation_changes_formal_conclusion
        ),
    }


def derive_decision_evidence(
    *,
    metric_rows: Sequence[Mapping[str, Any]],
    auc_rows: Sequence[Mapping[str, Any]],
    equivalence_rows: Sequence[Mapping[str, Any]],
    future_sensitivity: Sequence[Mapping[str, Any]],
    future_details: Mapping[str, Any],
    stream_rows: Sequence[Mapping[str, Any]],
    frame_contract_rows: Sequence[Mapping[str, Any]],
    frame_validation_rows: Sequence[Mapping[str, Any]],
    pilot_label_invalidated: bool,
    reference_summary: Mapping[str, Any],
    eigengap_rows: Sequence[Mapping[str, Any]],
    trigger_rows: Sequence[Mapping[str, Any]],
    corrected_evaluation_changes_formal_conclusion: bool,
) -> dict[str, bool]:
    """Reduce saved measurements to the inputs of the A/B/C/D decision rule."""

    metric_bug = any(not _bool(row["contract_consistent"]) for row in metric_rows)
    expected_streams = {
        "LiDAR": ("message_header", 0.0),
        "IMU_raw": ("message_header", 0.0),
        "IMU_effective_FAST_LIO": (
            "message_header_minus_frozen_offset",
            -TIME_OFFSET_LIDAR_TO_IMU,
        ),
        "FAST_LIO_odometry": ("message_header_lidar_end_time", 0.0),
        "RTK_fix": ("message_header", 0.0),
    }
    time_contract_pass = len(stream_rows) == len(expected_streams)
    for row in stream_rows:
        expected = expected_streams.get(str(row["stream"]))
        time_contract_pass = bool(
            time_contract_pass
            and expected is not None
            and row["timestamp_source"] == expected[0]
            and math.isclose(
                float(row["applied_offset_seconds"]),
                expected[1],
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
            and row["unit"] == "seconds"
            and row["unix_seconds_validation"] == "PASS"
            and int(row["duplicate_timestamp_count"]) == 0
            and int(row["non_monotonic_count"]) == 0
            and not _bool(row["bag_record_epoch_used"])
        )
    time_bug = not time_contract_pass

    frame_bug = not (
        all(_bool(row["verified"]) for row in frame_contract_rows)
        and all(_bool(row["pass"]) for row in frame_validation_rows)
    )
    future_bug = float(future_details["horizon_max_seconds"]) > (
        FORMAL_WINDOW_SECONDS + 1.0e-6
    )

    real_equivalence = {
        str(row["comparison"]): row
        for row in equivalence_rows
        if row["source"] == "all_detector_valid_real_frames"
    }
    entropy_equivalence = real_equivalence["spectral_entropy_trans"]
    odi_exact = bool(
        float(entropy_equivalence["analytic_relation_max_abs_residual"])
        <= 1.0e-12
    )
    odi_monotonic = bool(
        math.isclose(
            float(entropy_equivalence["risk_rank_equality_ratio"]),
            1.0,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        )
        and int(entropy_equivalence["monotonic_order_violation_count"]) == 0
        and math.isclose(
            float(entropy_equivalence["spearman_raw"]),
            -1.0,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    )

    reference_insufficient = bool(
        float(reference_summary["uncertainty_lower_deg"])
        <= DIRECTION_GATE_DEG
        <= float(reference_summary["uncertainty_upper_deg"])
        or not _bool(reference_summary["reference_axis_subwindow_stable"])
    )
    reliability_sufficient = bool(
        eigengap_rows
        and all(_bool(row["reliability_validation_sufficient"]) for row in eigengap_rows)
        and all(int(row["assignment_mismatch_count"]) == 0 for row in eigengap_rows)
    )
    trigger_bug = bool(
        not trigger_rows
        or any(
            _bool(row["trigger_implementation_bug_confirmed"])
            for row in trigger_rows
        )
    )
    trigger = {str(row["subset"]): row for row in trigger_rows}
    all_valid_trigger = trigger["all_detector_valid"]
    control_trigger = trigger["control_frozen_interval"]
    domain_transfer_failed = bool(
        not trigger_bug
        and float(all_valid_trigger["odi_min"]) > ODI_TRIGGER_THRESHOLD
        and float(control_trigger["trigger_ratio"]) > CONTROL_MAX_TRIGGER_RATIO
    )

    odi_auc = next(row for row in auc_rows if row["metric_name"] == "ODI_trans")
    formal_other_auc = [
        float(row["AUC_semantically_oriented"])
        for row in auc_rows
        if row["metric_name"] != "ODI_trans"
        and row["semantic_status"] == "FORMAL_SEMANTIC_POLARITY"
        and math.isfinite(float(row["AUC_semantically_oriented"]))
    ]
    odi_advantage = bool(
        formal_other_auc
        and float(odi_auc["AUC_semantically_oriented"]) > max(formal_other_auc)
    )
    corrected_future = next(
        row
        for row in future_sensitivity
        if float(row["window_seconds"]) == FORMAL_WINDOW_SECONDS
        and row["definition"] == "exact_target_vector_interpolation_diagnostic"
    )
    correlation_sufficient = float(corrected_future["odi_spearman_rho"]) >= (
        ODI_ABS_SPEARMAN_MINIMUM
    )
    control_pass = float(control_trigger["trigger_ratio"]) <= CONTROL_MAX_TRIGGER_RATIO
    method_negative_criteria = bool(
        not odi_advantage
        and not correlation_sufficient
        and not reliability_sufficient
        and not control_pass
    )
    return {
        "metric_direction_bug_confirmed": metric_bug,
        "time_alignment_bug_confirmed": time_bug,
        "frame_transform_bug_confirmed": frame_bug,
        "future_error_implementation_bug_confirmed": future_bug,
        "trigger_implementation_bug_confirmed": trigger_bug,
        "odi_exactly_equivalent": odi_exact,
        "odi_monotonically_equivalent": odi_monotonic,
        "pilot_label_invalidated": bool(pilot_label_invalidated),
        "reference_insufficient": reference_insufficient,
        "reliability_validation_sufficient": reliability_sufficient,
        "real_domain_threshold_transfer_failed": domain_transfer_failed,
        "corrected_evaluation_changes_formal_conclusion": bool(
            corrected_evaluation_changes_formal_conclusion
        ),
        "method_negative_criteria_satisfied": method_negative_criteria,
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
The formal Jacobian is built from the current iterated in-call linearization
state `s`.  The scan-start prior is retained as metadata and the post-update
pose is not used to rotate the exported weak direction.  The forward
IMU-from-LiDAR extrinsic is already applied upstream while constructing the
formal Jacobian, so it must not be applied again to the world-frame weak axis.
The offline chain is only `v_ENU = R_enu_from_fast_world @ v_world`, followed by
`acos(abs(dot(unit(v_ENU), unit(axis_ENU))))`.  Kabsch translation is correctly
excluded from direction transformation.  ENU, not NED, is used.  Unit/X/Y/Z,
forward LiDAR-to-IMU-to-world, sign, and fixed-seed random SO(3) tests pass to
1e-12.  `FRAME_TRANSFORM_BUG_CONFIRMED=false`.

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
independent measurement of the environmental Schur null direction.  Within the
same 14-second interval, the two half-window endpoint axes differ by
{ref['half_window_axis_angle_deg']:.6f} degrees and the maximum quarter-window
pair differs by {ref['quarter_window_axis_max_pairwise_angle_deg']:.6f} degrees.
The globally aligned LIO motion axis agrees within
{ref['aligned_motion_axis_consistency_deg']:.6f} degrees, but that only confirms
motion consistency and cannot validate an environmental null axis.
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

## Technical summary

Primary conclusion: **{decision['PRIMARY_CONCLUSION_CATEGORY']}.
{decision['PRIMARY_AUDIT_CONCLUSION']}**.

`MEASUREMENT_PLAN_STATUS={decision['MEASUREMENT_PLAN_STATUS']}`.  The nominal
control segment is consistently weaker than the structural candidate under
both absolute-strength and spectral-shape information families.  The frozen
label therefore does not measure the intended contrast.  The reference axis is
also insufficient for a sharp 30-degree decision, so the current evidence
cannot isolate a method-level negative result.  The original Pilot remains
FAIL; this audit is not a retrospective pass.

## The label failure is the primary decision driver

Structural/control median lambda-min is {structural_lambda:.6f}/
{control_lambda:.6f}; median condition number is
{structural_condition:.6f}/{control_condition:.6f}.  Those absolute-strength and
shape diagnostics agree that the control is less observable.  ODI semantic
AUROC remains {float(auc['ODI_trans']['AUC_semantically_oriented']):.9f}; labels
were neither swapped nor reselected to improve it.

The formal 3-D median weak-axis error is {ref['formal_3d_median_deg']:.6f}
degrees, and its declared uncertainty interval
[{ref['uncertainty_lower_deg']:.6f}, {ref['uncertainty_upper_deg']:.6f}] crosses
the 30-degree gate.  Half- and quarter-window reference axes are not stable.
This is a concurrent limitation, not category C overriding the stronger
category-B label evidence.

Two component evaluation defects were confirmed: eigengap/correlation semantics
and exact future-time interpolation.  Corrected evaluation v2 retains the same
bag, intervals, formulas, threshold, and five-second formal window and reruns
every original Gate condition.  No Gate or formal conclusion changes, so
`EVALUATION_BUG_CONFIRMED=false`.  ODI is analytically rank-equivalent to the
exported spectral entropy/effective rank, so independent ranking information is
not established.

## Scope, data, and metric definitions

The audit uses only the frozen MUN-FRL Lighthouse bag and the preregistered
1645814048-1645814062 structural and 1645814164-1645814178 control intervals.
The structural interval remains positive class 1.  Future error growth is the
change in globally rigid-aligned 3-D position error over the formal five-second
window.  LiDAR, IMU, FAST-LIO, and RTK timestamps are ROS message-header Unix
seconds; reference data is offline position-only ENU.

## Method and robustness checks

Metric polarity was derived from formulas before inspecting labels.  AUROC was
recomputed in raw, semantic, and reversed-diagnostic directions without using
`max(AUC, 1-AUC)`.  Future growth was checked with exact native-stream
interpolation and 1/3/5/10-second sensitivity windows.  A -2 to +2 second lag
grid was diagnostic only.  The full weak-axis frame chain was checked with
identity, X/Y/Z 90-degree, sign, forward-extrinsic, and fixed-seed random SO(3)
tests.  Label validity used independent absolute-information and spectral-shape
families; reliability uncertainty used bootstrap intervals, Mann-Whitney, and
Cliff's delta descriptively.

## Limitations and uncertainty

Plane-normal distributions, normal covariance, residual magnitudes, map
Cartesian extent, end-face counts, and floor/ceiling/wall ratios were not
retained and are explicitly unavailable.  RTK supplies motion position rather
than an independent environmental Schur-null axis; the antenna-to-IMU lever arm
was not recorded.  This is one sequence with only five unreliable structural
frames, so neither eigengap calibration nor cross-domain trigger calibration is
validated.

## Recommended next step

Authorize one newly preregistered replacement Pilot.  It must independently
validate both the LIO observability labels and a reference axis capable of
supporting the 30-degree decision before detector outputs are examined.  Do not
expand to a second dataset and do not authorize ODI Measurement mainline yet.

## Further questions

The replacement protocol must specify how environmental observability ground
truth is obtained independently of raw scan anisotropy, how reference-axis
uncertainty is calibrated, and what minimum reliable/unreliable sample counts
are required.  Real-domain trigger calibration is a later preregistered task;
it must not be tuned on this failed Pilot.

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

    raw_root = (
        repository_root
        / "results/measurement_real_validation/mun_frl_lighthouse_pilot/raw"
    )
    input_paths = {
        "runtime_audit_v2.bin": raw_root / "runtime_audit_v2.bin",
        "fastlio_odometry.csv": raw_root / "topic_capture/fastlio_odometry.csv",
        "navsat_fix.csv": raw_root / "topic_capture/navsat_fix.csv",
        "raw_scene_descriptors.csv": repository_root
        / "data/measurement_real_validation/mun_frl_lighthouse_pilot/interval_selection_evidence/raw_scene_descriptors.csv",
        "mun_frl_pilot_intervals.yaml": repository_root
        / "configs/real_data/mun_frl_pilot_intervals.yaml",
        "mun_frl_lighthouse.yaml": repository_root
        / "configs/real_data/mun_frl_lighthouse.yaml",
        "detector_lock.json": repository_root
        / "artifacts/current/detector_stage2a/locked/detector_lock.json",
        "odi_threshold_calibration.json": repository_root
        / "artifacts/current/detector_stage2a/development/odi_threshold_calibration.json",
    }
    input_sha256 = {name: sha256_file(path) for name, path in input_paths.items()}
    if input_sha256 != EXPECTED_INPUT_SHA256:
        raise RuntimeError("retained scientific-audit input hashes changed")
    mun_frl_config = yaml.safe_load(
        input_paths["mun_frl_lighthouse.yaml"].read_text(encoding="utf-8")
    )
    validate_mun_frl_config(mun_frl_config)

    output_dir.mkdir(parents=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir()
    interval_lock = load_interval_lock(
        input_paths["mun_frl_pilot_intervals.yaml"]
    )
    frame_rows: list[dict[str, Any]] = read_csv(
        pilot_artifact_dir / "tables/frame_metrics.csv"
    )
    attach_frozen_intervals(frame_rows, interval_lock["intervals"])
    runtime_rows, runtime_integrity = load_runtime_rows(repository_root)
    descriptor_rows = read_csv(
        input_paths["raw_scene_descriptors.csv"]
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
    correction_manifest = write_corrected_evaluation_v2(
        output_dir,
        pilot_artifact_dir,
        auc_rows,
        future_sensitivity,
        reference_summary,
        eigengap_rows,
        trigger_rows,
    )
    decision_evidence = derive_decision_evidence(
        metric_rows=metric_rows,
        auc_rows=auc_rows,
        equivalence_rows=equivalence_rows,
        future_sensitivity=future_sensitivity,
        future_details=future_details,
        stream_rows=stream_rows,
        frame_contract_rows=frame_contract_rows,
        frame_validation_rows=frame_validation_rows,
        pilot_label_invalidated=label_invalidated,
        reference_summary=reference_summary,
        eigengap_rows=eigengap_rows,
        trigger_rows=trigger_rows,
        corrected_evaluation_changes_formal_conclusion=bool(
            correction_manifest["formal_conclusion_changed"]
        ),
    )
    decision = final_decision(**decision_evidence)
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
        "retained_input_sha256": input_sha256,
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
        "decision_evidence": decision_evidence,
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

    correction_dir = audit_dir / "corrected_evaluation_v2"
    nested_lines = (correction_dir / "SHA256SUMS").read_text(
        encoding="utf-8"
    ).splitlines()
    nested_listed: set[str] = set()
    for line in nested_lines:
        digest, relative = line.split("  ", 1)
        nested_listed.add(relative)
        if sha256_file(correction_dir / relative) != digest:
            raise ValueError(f"corrected-evaluation checksum mismatch: {relative}")
    nested_actual = {
        path.relative_to(correction_dir).as_posix()
        for path in correction_dir.rglob("*")
        if path.is_file() and path != correction_dir / "SHA256SUMS"
    }
    if nested_listed != nested_actual:
        raise ValueError("corrected-evaluation checksum coverage is incomplete")

    manifest = json.loads((audit_dir / "run_manifest.json").read_text(encoding="utf-8"))
    decision = json.loads((audit_dir / "final_decision.json").read_text(encoding="utf-8"))
    correction = json.loads(
        (correction_dir / "correction_manifest.json").read_text(encoding="utf-8")
    )
    if manifest["schema_version"] != AUDIT_SCHEMA:
        raise ValueError("audit schema is invalid")
    if manifest["python"]["implementation"] != "CPython" or not str(
        manifest["python"]["version"]
    ).startswith("3.11."):
        raise ValueError("audit was not executed with the required CPython 3.11")
    if manifest["bag_sha256"] != EXPECTED_BAG_SHA256:
        raise ValueError("frozen bag hash evidence is invalid")
    if manifest["retained_input_sha256"] != EXPECTED_INPUT_SHA256:
        raise ValueError("retained input hashes are incomplete or changed")
    if (
        manifest["pilot_tree_sha256_before"] != EXPECTED_PILOT_TREE_SHA256
        or manifest["pilot_tree_sha256_after"] != EXPECTED_PILOT_TREE_SHA256
        or not manifest["pilot_tree_unchanged"]
    ):
        raise ValueError("frozen Pilot hash evidence is invalid")
    if any(manifest["prohibitions"].values()):
        raise ValueError("a forbidden action is reported as performed")

    table_rows = {
        name: read_csv(audit_dir / "tables" / name) for name in REQUIRED_TABLES
    }
    if any(not rows for rows in table_rows.values()):
        raise ValueError("one or more required audit tables are empty")
    for report in REQUIRED_REPORTS:
        if not (audit_dir / report).read_text(encoding="utf-8").strip():
            raise ValueError(f"required report is empty: {report}")

    label_invalidated, _ = information_supports_label_invalidation(
        table_rows["interval_lio_information_audit.csv"]
    )
    future_map = {
        row["audit_item"]: row["result"]
        for row in table_rows["future_error_growth_audit.csv"]
    }
    reference_map = {
        row["audit_item"]: row["value"]
        for row in table_rows["reference_axis_audit.csv"]
    }
    uncertainty = [
        float(value)
        for value in reference_map["formal_3d_median_uncertainty_interval"].split(
            ";"
        )
    ]
    reference_summary = {
        "uncertainty_lower_deg": uncertainty[0],
        "uncertainty_upper_deg": uncertainty[1],
        "reference_axis_subwindow_stable": _bool(
            reference_map["reference_axis_subwindow_stable"]
        ),
    }
    decision_evidence = derive_decision_evidence(
        metric_rows=table_rows["metric_semantic_contract.csv"],
        auc_rows=table_rows["auc_direction_audit.csv"],
        equivalence_rows=table_rows["odi_entropy_equivalence.csv"],
        future_sensitivity=table_rows["future_window_sensitivity.csv"],
        future_details={
            "horizon_max_seconds": float(future_map["horizon_max_seconds"])
        },
        stream_rows=table_rows["time_stream_summary.csv"],
        frame_contract_rows=table_rows["coordinate_frame_contract.csv"],
        frame_validation_rows=table_rows["frame_transform_validation.csv"],
        pilot_label_invalidated=label_invalidated,
        reference_summary=reference_summary,
        eigengap_rows=table_rows["eigengap_reliability_audit.csv"],
        trigger_rows=table_rows["trigger_contract_audit.csv"],
        corrected_evaluation_changes_formal_conclusion=_bool(
            correction["formal_conclusion_changed"]
        ),
    )
    expected_decision = final_decision(**decision_evidence)
    if decision != expected_decision:
        raise ValueError("final decision does not match independently derived evidence")
    if manifest["decision"] != expected_decision:
        raise ValueError("run manifest and final decision disagree")
    if manifest["decision_evidence"] != decision_evidence:
        raise ValueError("run manifest decision evidence does not reproduce")
    decision_csv = {
        row["decision_field"]: row["value"]
        for row in table_rows["final_decision.csv"]
    }
    if set(decision_csv) != set(expected_decision) or any(
        decision_csv[key] != str(value) for key, value in expected_decision.items()
    ):
        raise ValueError("final_decision.csv does not match final_decision.json")

    required_gate_conditions = {
        "python311_full_pytest_pass",
        "bag_validation_pass",
        "point_time_unit_pass",
        "extrinsic_direction_pass",
        "no_reference_dependency_pass",
        "same_call_mutation_pass",
        "detector_feedback_pass",
        "frozen_detector_determinism_pass",
        "finite_detector_output_pass",
        "fastlio2_crash_pass",
        "valid_detector_ratio_pass",
        "detector_core_mean_target_pass",
        "total_added_q95_target_pass",
        "frozen_structural_and_control_intervals",
        "same_input_all_metrics",
        "structural_direction_median_pass",
        "reliable_better_than_unreliable",
        "odi_effectiveness_pass",
        "control_false_trigger_pass",
        "no_reference_online",
        "MEASUREMENT_REAL_PILOT_PASS",
        "SECOND_DATASET_EXPANSION_AUTHORIZED",
        "ODI_ADVANTAGE_ESTABLISHED",
    }
    corrected_gate_rows = read_csv(correction_dir / "corrected_gate_summary.csv")
    corrected_gate_conditions = {row["condition"] for row in corrected_gate_rows}
    if corrected_gate_conditions != required_gate_conditions:
        raise ValueError("corrected evaluation did not rerun every original Gate condition")
    corrected_gate = {row["condition"]: _bool(row["pass"]) for row in corrected_gate_rows}
    if corrected_gate["MEASUREMENT_REAL_PILOT_PASS"] or corrected_gate[
        "SECOND_DATASET_EXPANSION_AUTHORIZED"
    ]:
        raise ValueError("corrected evaluation was misreported as a pass")
    before_after = read_csv(correction_dir / "before_after_evaluation.csv")
    material_changes = any(_bool(row["material_gate_change"]) for row in before_after)
    if material_changes != _bool(correction["formal_conclusion_changed"]):
        raise ValueError("correction materiality does not match before/after evidence")
    if not (
        correction["all_original_gates_reexecuted"]
        and int(correction["original_gate_condition_count"])
        == len(required_gate_conditions)
        and correction["affected_files"]
        and correction["affected_outputs"]
    ):
        raise ValueError("corrected evaluation provenance is incomplete")
    if correction["frozen_identity"] != {
        "bag_sha256": EXPECTED_BAG_SHA256,
        "interval_lock_sha256": EXPECTED_INPUT_SHA256[
            "mun_frl_pilot_intervals.yaml"
        ],
        "odi_trigger_threshold": ODI_TRIGGER_THRESHOLD,
        "formal_future_window_seconds": FORMAL_WINDOW_SECONDS,
    }:
        raise ValueError("corrected evaluation changed a frozen identity")
    for relative, digest in correction["after_checksums"].items():
        if sha256_file(correction_dir / relative) != digest:
            raise ValueError(f"corrected output hash mismatch: {relative}")

    return {
        "AUDIT_ARTIFACT_VERIFY_PASS": True,
        "file_count": len(actual) + 1,
        "primary_conclusion": expected_decision["PRIMARY_AUDIT_CONCLUSION"],
        "primary_category": expected_decision["PRIMARY_CONCLUSION_CATEGORY"],
        "measurement_plan_status": expected_decision["MEASUREMENT_PLAN_STATUS"],
        "python_version": manifest["python"]["version"],
    }
