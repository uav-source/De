"""Trajectory and window metrics for the Day 8 synthetic probe.

This module intentionally evaluates only saved trajectory and detector outputs:
TUM pose files, GT pose files, axis.csv, and ODI CSV values. It does not import
the Day 7 estimator or reuse any estimator-side summary.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, Iterable, Union

import numpy as np


ArrayLikePath = Union[str, Path]


def load_tum_pose(path: ArrayLikePath) -> np.ndarray:
    """Load a TUM pose file with columns timestamp tx ty tz qx qy qz qw."""

    pose_path = Path(path)
    poses = np.loadtxt(pose_path, dtype=float)
    if poses.ndim == 1:
        poses = poses.reshape(1, -1)
    if poses.ndim != 2 or poses.shape[1] != 8:
        raise ValueError(f"TUM pose file must have shape [N, 8]: {pose_path}")
    _validate_finite("tum_pose", poses)
    quat_norm = np.linalg.norm(poses[:, 4:8], axis=1)
    if np.any(quat_norm < 1.0e-12):
        raise ValueError(f"TUM pose file contains zero quaternion: {pose_path}")
    normalized = poses.copy()
    normalized[:, 4:8] /= quat_norm[:, None]
    return normalized


def load_axis_csv(path: ArrayLikePath) -> np.ndarray:
    """Load normalized local axes from axis.csv."""

    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append([float(row["axis_x"]), float(row["axis_y"]), float(row["axis_z"])])
    if not rows:
        raise ValueError(f"axis.csv has no rows: {path}")
    axis = normalize_rows(np.asarray(rows, dtype=float))
    _validate_finite("axis", axis)
    return axis


def align_se3_if_needed(est: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Align an estimated trajectory to GT by the first SE(3) pose if needed."""

    est = _validate_pose_array("est", est)
    gt = _validate_pose_array("gt", gt)
    _require_same_length_and_timestamps(est, gt)

    r_est0 = quat_to_rot(est[0, 4:8])
    r_gt0 = quat_to_rot(gt[0, 4:8])
    first_position_delta = np.linalg.norm(est[0, 1:4] - gt[0, 1:4])
    first_rotation_delta = np.linalg.norm(r_est0 - r_gt0)
    if first_position_delta < 1.0e-10 and first_rotation_delta < 1.0e-10:
        return est.copy()

    r_align = r_gt0 @ r_est0.T
    t_align = gt[0, 1:4] - r_align @ est[0, 1:4]

    aligned = est.copy()
    aligned[:, 1:4] = (r_align @ est[:, 1:4].T).T + t_align
    for idx in range(est.shape[0]):
        aligned[idx, 4:8] = rot_to_quat(r_align @ quat_to_rot(est[idx, 4:8]))
    return aligned


def compute_ATE(est: np.ndarray, gt: np.ndarray) -> float:
    """Compute translational Absolute Trajectory Error RMSE."""

    est = _validate_pose_array("est", est)
    gt = _validate_pose_array("gt", gt)
    _require_same_length_and_timestamps(est, gt)
    error = est[:, 1:4] - gt[:, 1:4]
    return float(np.sqrt(np.mean(np.sum(error * error, axis=1))))


def compute_RPE(est: np.ndarray, gt: np.ndarray, window: int) -> np.ndarray:
    """Compute translational relative pose error over a fixed frame window."""

    est = _validate_pose_array("est", est)
    gt = _validate_pose_array("gt", gt)
    _require_same_length_and_timestamps(est, gt)
    if int(window) < 1:
        raise ValueError("RPE window must be >= 1")
    window = int(window)
    if est.shape[0] <= window:
        return np.zeros(0, dtype=float)
    est_delta = est[window:, 1:4] - est[:-window, 1:4]
    gt_delta = gt[window:, 1:4] - gt[:-window, 1:4]
    rpe = np.linalg.norm(est_delta - gt_delta, axis=1)
    _validate_finite("RPE", rpe)
    return rpe


def compute_axis_error(est: np.ndarray, gt: np.ndarray, axis_per_frame: np.ndarray) -> np.ndarray:
    """Compute e_axis(t) = |a(t)^T (p_est(t) - p_gt(t))|."""

    error, axis = _translation_error_and_axis(est, gt, axis_per_frame)
    signed_projection = np.einsum("ij,ij->i", error, axis)
    axis_error = np.abs(signed_projection)
    _validate_finite("axis_error", axis_error)
    return axis_error


def compute_cross_error(est: np.ndarray, gt: np.ndarray, axis_per_frame: np.ndarray) -> np.ndarray:
    """Compute cross-track error from the signed axis projection."""

    error, axis = _translation_error_and_axis(est, gt, axis_per_frame)
    signed_projection = np.einsum("ij,ij->i", error, axis)
    cross_vector = error - signed_projection[:, None] * axis
    cross_error = np.linalg.norm(cross_vector, axis=1)
    _validate_finite("cross_error", cross_error)
    return cross_error


def compute_sliding_window_drift_rate(
    error_series: np.ndarray,
    path_length: np.ndarray,
    window_size: int,
    stride: int,
) -> np.ndarray:
    """Compute signed error growth per meter for fixed-size sliding windows."""

    error_series = _as_1d_float("error_series", error_series)
    path_length = _as_1d_float("path_length", path_length)
    if error_series.shape[0] != path_length.shape[0]:
        raise ValueError("error_series and path_length must have the same length")
    if np.any(np.diff(path_length) < -1.0e-9):
        raise ValueError("path_length must be monotonic non-decreasing")
    if int(window_size) < 2:
        raise ValueError("window_size must be >= 2")
    if int(stride) < 1:
        raise ValueError("stride must be >= 1")
    window_size = int(window_size)
    stride = int(stride)

    dtype = [
        ("start_idx", "i4"),
        ("end_idx", "i4"),
        ("path_length", "f8"),
        ("error_start", "f8"),
        ("error_end", "f8"),
        ("drift_rate", "f8"),
    ]
    if error_series.shape[0] < window_size:
        return np.zeros(0, dtype=dtype)

    rows = []
    for start in range(0, error_series.shape[0] - window_size + 1, stride):
        end = start + window_size - 1
        window_path = float(path_length[end] - path_length[start])
        drift_rate = 0.0
        if window_path > 1.0e-12:
            drift_rate = float((error_series[end] - error_series[start]) / window_path)
        rows.append(
            (
                start,
                end,
                window_path,
                float(error_series[start]),
                float(error_series[end]),
                drift_rate,
            )
        )
    return np.asarray(rows, dtype=dtype)


def compute_window_samples_for_correlation(
    ODI_series: np.ndarray,
    axis_error_series: np.ndarray,
    weak_error_series: np.ndarray,
) -> np.ndarray:
    """Return finite aligned samples for later per-sequence correlation checks."""

    odi = _as_1d_float("ODI_series", ODI_series)
    axis_error = _as_1d_float("axis_error_series", axis_error_series)
    weak_error = _as_1d_float("weak_error_series", weak_error_series)
    if not (odi.shape[0] == axis_error.shape[0] == weak_error.shape[0]):
        raise ValueError("Correlation input series must have the same length")

    finite = np.isfinite(odi) & np.isfinite(axis_error) & np.isfinite(weak_error)
    dtype = [("ODI", "f8"), ("axis_error", "f8"), ("weak_error", "f8")]
    rows = np.zeros(int(np.sum(finite)), dtype=dtype)
    rows["ODI"] = odi[finite]
    rows["axis_error"] = axis_error[finite]
    rows["weak_error"] = weak_error[finite]
    return rows


def compute_cumulative_path_length(poses: np.ndarray) -> np.ndarray:
    poses = _validate_pose_array("poses", poses)
    cumulative = np.zeros(poses.shape[0], dtype=float)
    if poses.shape[0] > 1:
        step = np.linalg.norm(np.diff(poses[:, 1:4], axis=0), axis=1)
        cumulative[1:] = np.cumsum(step)
    return cumulative


def normalize_rows(values: np.ndarray, eps: float = 1.0e-12) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    _validate_finite("values", values)
    if values.ndim != 2:
        raise ValueError("values must be a 2-D array")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms[:, 0] < eps):
        raise ValueError("Cannot normalize zero-length row")
    return values / norms


def quat_to_rot(qxyzw: Iterable[float]) -> np.ndarray:
    x, y, z, w = [float(v) for v in qxyzw]
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1.0e-12:
        raise ValueError("Invalid zero quaternion")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=float,
    )


def rot_to_quat(rotation: np.ndarray) -> np.ndarray:
    rotation = np.asarray(rotation, dtype=float)
    _validate_finite("rotation", rotation)
    trace = float(np.trace(rotation))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (rotation[2, 1] - rotation[1, 2]) / s
        qy = (rotation[0, 2] - rotation[2, 0]) / s
        qz = (rotation[1, 0] - rotation[0, 1]) / s
    else:
        diag = np.diag(rotation)
        idx = int(np.argmax(diag))
        if idx == 0:
            s = math.sqrt(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]) * 2.0
            qw = (rotation[2, 1] - rotation[1, 2]) / s
            qx = 0.25 * s
            qy = (rotation[0, 1] + rotation[1, 0]) / s
            qz = (rotation[0, 2] + rotation[2, 0]) / s
        elif idx == 1:
            s = math.sqrt(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]) * 2.0
            qw = (rotation[0, 2] - rotation[2, 0]) / s
            qx = (rotation[0, 1] + rotation[1, 0]) / s
            qy = 0.25 * s
            qz = (rotation[1, 2] + rotation[2, 1]) / s
        else:
            s = math.sqrt(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]) * 2.0
            qw = (rotation[1, 0] - rotation[0, 1]) / s
            qx = (rotation[0, 2] + rotation[2, 0]) / s
            qy = (rotation[1, 2] + rotation[2, 1]) / s
            qz = 0.25 * s
    quat = np.array([qx, qy, qz, qw], dtype=float)
    return quat / np.linalg.norm(quat)


def summarize_odi_table(odi_table: Dict[str, np.ndarray]) -> Dict[str, float]:
    required = ["ODI", "AIS", "lambda_min", "condition_number"]
    for key in required:
        if key not in odi_table:
            raise ValueError(f"ODI table missing required field: {key}")
        _as_1d_float(key, odi_table[key])
    if "lambda_min_clamped" in odi_table:
        lambda_min_clamped = _as_1d_float("lambda_min_clamped", odi_table["lambda_min_clamped"])
    else:
        lambda_min_clamped = np.maximum(odi_table["lambda_min"], 0.0)
    return {
        "ODI_mean": float(np.mean(odi_table["ODI"])),
        "ODI_median": float(np.median(odi_table["ODI"])),
        "AIS_mean": float(np.mean(odi_table["AIS"])),
        "lambda_min_median": float(np.median(odi_table["lambda_min"])),
        "lambda_min_clamped_median": float(np.median(lambda_min_clamped)),
        "condition_number_median": float(np.median(odi_table["condition_number"])),
    }


def _translation_error_and_axis(
    est: np.ndarray,
    gt: np.ndarray,
    axis_per_frame: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    est = _validate_pose_array("est", est)
    gt = _validate_pose_array("gt", gt)
    _require_same_length_and_timestamps(est, gt)
    axis = normalize_rows(np.asarray(axis_per_frame, dtype=float))
    if axis.shape != (est.shape[0], 3):
        raise ValueError(f"axis_per_frame must have shape [N, 3], got {axis.shape}")
    error = est[:, 1:4] - gt[:, 1:4]
    _validate_finite("translation_error", error)
    return error, axis


def _validate_pose_array(name: str, poses: np.ndarray) -> np.ndarray:
    poses = np.asarray(poses, dtype=float)
    if poses.ndim != 2 or poses.shape[1] != 8:
        raise ValueError(f"{name} must have shape [N, 8], got {poses.shape}")
    _validate_finite(name, poses)
    quat_norm = np.linalg.norm(poses[:, 4:8], axis=1)
    if np.any(quat_norm < 1.0e-12):
        raise ValueError(f"{name} contains a zero quaternion")
    return poses


def _require_same_length_and_timestamps(est: np.ndarray, gt: np.ndarray) -> None:
    if est.shape[0] != gt.shape[0]:
        raise ValueError(f"Pose counts differ: est={est.shape[0]}, gt={gt.shape[0]}")
    if not np.allclose(est[:, 0], gt[:, 0], atol=1.0e-6, rtol=0.0):
        raise ValueError("Estimated and GT timestamps do not match")


def _as_1d_float(name: str, values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1-D array")
    _validate_finite(name, array)
    return array


def _validate_finite(name: str, values: np.ndarray) -> None:
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} contains NaN or Inf")
