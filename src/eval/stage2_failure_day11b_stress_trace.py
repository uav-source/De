"""Read-only per-frame stress and frozen-Huber mechanism diagnostics."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from eval.stage2_failure_schema import FRAME_KEY_FIELDS
from minibench.map_lio import linearize_point_to_plane
from minibench.update_strategies import build_robust_linear_system


STRESS_TRACE_SCHEMA_VERSION = "stage2_failure_day11b_stress_trace_v1"
STRESS_TRACE_FIELDS = (
    "schema_version", *FRAME_KEY_FIELDS, "stress_active",
    "contaminated_measurement_count", "contaminated_measurement_ratio",
    "contamination_offset_signed_mean_m", "contamination_offset_abs_mean_m",
    "contamination_offset_abs_max_m", "contaminated_normalized_residual_mean",
    "contaminated_normalized_residual_median", "contaminated_normalized_residual_abs_median",
    "contaminated_normalized_residual_abs_max", "contaminated_positive_count",
    "contaminated_negative_count", "contaminated_dominant_sign_ratio",
    "contaminated_huber_downweighted_count", "contaminated_huber_downweighted_ratio",
    "contaminated_subhuber_count", "contaminated_subhuber_ratio",
    "all_huber_outlier_ratio", "all_mean_huber_weight", "all_min_huber_weight",
)


def compute_stress_trace(
    online_records: Sequence[Mapping[str, Any]],
    prior_poses: np.ndarray,
    observations: Mapping[str, Any],
    huber_delta_sigma: float,
) -> Sequence[Mapping[str, Any]]:
    """Re-linearize frozen observations at recorded priors without changing state."""

    priors = np.asarray(prior_poses, dtype=float)
    points = np.asarray(observations["points_lidar"], dtype=float)
    normals = np.asarray(observations["normals_world"], dtype=float)
    anchors = np.asarray(observations["plane_points_world"], dtype=float)
    residual_noise = np.asarray(observations["r_list"], dtype=float)
    variances = np.asarray(observations["R_diag_list"], dtype=float)
    mask_all = np.asarray(observations["contamination_mask"], dtype=bool)
    offsets_all = np.asarray(observations["contamination_offset_m"], dtype=float)
    rows = []
    for online in online_records:
        frame = int(online["frame_index"])
        jacobian, residual = linearize_point_to_plane(
            priors[frame], points[frame], normals[frame], anchors[frame], residual_noise[frame]
        )
        robust = build_robust_linear_system(
            jacobian, residual, variances[frame], float(huber_delta_sigma)
        )
        weights = np.asarray(robust.robust_weights, dtype=float)
        normalized = residual / np.sqrt(variances[frame])
        mask = mask_all[frame]
        offsets = offsets_all[frame][mask]
        contaminated = normalized[mask]
        count = int(np.count_nonzero(mask))
        nan = float("nan")
        if count:
            positive = int(np.count_nonzero(contaminated > 0.0))
            negative = int(np.count_nonzero(contaminated < 0.0))
            nonzero = positive + negative
            downweighted = int(np.count_nonzero(weights[mask] < 1.0))
            subhuber = int(np.count_nonzero(np.abs(contaminated) <= float(huber_delta_sigma)))
            contaminated_values = {
                "contamination_offset_signed_mean_m": float(np.mean(offsets)),
                "contamination_offset_abs_mean_m": float(np.mean(np.abs(offsets))),
                "contamination_offset_abs_max_m": float(np.max(np.abs(offsets))),
                "contaminated_normalized_residual_mean": float(np.mean(contaminated)),
                "contaminated_normalized_residual_median": float(np.median(contaminated)),
                "contaminated_normalized_residual_abs_median": float(np.median(np.abs(contaminated))),
                "contaminated_normalized_residual_abs_max": float(np.max(np.abs(contaminated))),
                "contaminated_positive_count": positive,
                "contaminated_negative_count": negative,
                "contaminated_dominant_sign_ratio": max(positive, negative) / nonzero if nonzero else nan,
                "contaminated_huber_downweighted_count": downweighted,
                "contaminated_huber_downweighted_ratio": downweighted / count,
                "contaminated_subhuber_count": subhuber,
                "contaminated_subhuber_ratio": subhuber / count,
            }
        else:
            contaminated_values = {
                "contamination_offset_signed_mean_m": nan,
                "contamination_offset_abs_mean_m": nan,
                "contamination_offset_abs_max_m": nan,
                "contaminated_normalized_residual_mean": nan,
                "contaminated_normalized_residual_median": nan,
                "contaminated_normalized_residual_abs_median": nan,
                "contaminated_normalized_residual_abs_max": nan,
                "contaminated_positive_count": 0,
                "contaminated_negative_count": 0,
                "contaminated_dominant_sign_ratio": nan,
                "contaminated_huber_downweighted_count": 0,
                "contaminated_huber_downweighted_ratio": nan,
                "contaminated_subhuber_count": 0,
                "contaminated_subhuber_ratio": nan,
            }
        row = {
            "schema_version": STRESS_TRACE_SCHEMA_VERSION,
            **{field: online[field] for field in FRAME_KEY_FIELDS},
            "stress_active": bool(count > 0),
            "contaminated_measurement_count": count,
            "contaminated_measurement_ratio": float(count / mask.size),
            **contaminated_values,
            "all_huber_outlier_ratio": float(np.mean(weights < 1.0)),
            "all_mean_huber_weight": float(np.mean(weights)),
            "all_min_huber_weight": float(np.min(weights)),
        }
        validate_stress_trace_record(row)
        rows.append(row)
    return rows


def validate_stress_trace_record(record: Mapping[str, Any]) -> None:
    if set(record) != set(STRESS_TRACE_FIELDS):
        raise ValueError("Day 11B stress trace schema changed")
    if record["schema_version"] != STRESS_TRACE_SCHEMA_VERSION:
        raise ValueError("Day 11B stress trace schema version changed")
    count = int(record["contaminated_measurement_count"])
    ratio = float(record["contaminated_measurement_ratio"])
    if count < 0 or not 0.0 <= ratio <= 1.0:
        raise ValueError("invalid contamination count or ratio")
    if bool(record["stress_active"]) != (count > 0):
        raise ValueError("stress_active does not match contamination count")
    contaminated_float_fields = (
        "contamination_offset_signed_mean_m", "contamination_offset_abs_mean_m",
        "contamination_offset_abs_max_m", "contaminated_normalized_residual_mean",
        "contaminated_normalized_residual_median", "contaminated_normalized_residual_abs_median",
        "contaminated_normalized_residual_abs_max", "contaminated_dominant_sign_ratio",
        "contaminated_huber_downweighted_ratio", "contaminated_subhuber_ratio",
    )
    if count == 0:
        if any(not math.isnan(float(record[field])) for field in contaminated_float_fields):
            raise ValueError("uncontaminated trace metrics must be NaN")
    elif any(not math.isfinite(float(record[field])) for field in contaminated_float_fields):
        raise ValueError("contaminated trace metrics must be finite")
    for field in ("all_huber_outlier_ratio", "all_mean_huber_weight", "all_min_huber_weight"):
        if not math.isfinite(float(record[field])):
            raise ValueError(f"stress trace field {field} must be finite")
