"""Fixed CSV schemas and validators for Stage 2 Day 8 diagnostics."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


ONLINE_SCHEMA_VERSION = "stage2_failure_online_v1"
GT_SCHEMA_VERSION = "stage2_failure_gt_v1"

FRAME_KEY_FIELDS = [
    "run_id",
    "sequence_id",
    "sweep",
    "level",
    "stress",
    "geometry_seed",
    "sensor_seed",
    "process_seed",
    "method",
    "frame_index",
    "timestamp",
]

ONLINE_FIELDS = [
    "schema_version",
    *FRAME_KEY_FIELDS,
    "weak_direction_valid",
    "weak_direction_raw_world_x",
    "weak_direction_raw_world_y",
    "weak_direction_raw_world_z",
    "weak_direction_logged_world_x",
    "weak_direction_logged_world_y",
    "weak_direction_logged_world_z",
    "weak_direction_sign_flipped",
    "odi_trans",
    "primary_eigengap_ratio",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
    "weak_innovation_valid",
    "weak_score_gradient_raw",
    "weak_score_information_raw",
    "weak_innovation_z_raw",
    "weak_score_gradient_huber",
    "weak_score_information_huber",
    "weak_innovation_z_huber",
    "residual_count",
    "huber_outlier_count",
    "huber_outlier_ratio",
    "mean_huber_weight",
    "min_huber_weight",
    "full_delta_theta_x",
    "full_delta_theta_y",
    "full_delta_theta_z",
    "full_delta_p_x",
    "full_delta_p_y",
    "full_delta_p_z",
    "full_update_weak_signed_m",
    "full_update_weak_abs_m",
    "full_update_strong_x",
    "full_update_strong_y",
    "full_update_strong_z",
    "full_update_strong_norm_m",
    "full_update_rotation_norm_rad",
    "applied_strategy",
    "applied_delta_theta_x",
    "applied_delta_theta_y",
    "applied_delta_theta_z",
    "applied_delta_p_x",
    "applied_delta_p_y",
    "applied_delta_p_z",
    "applied_update_weak_signed_m",
    "applied_update_weak_abs_m",
    "applied_update_strong_x",
    "applied_update_strong_y",
    "applied_update_strong_z",
    "applied_update_strong_norm_m",
    "applied_update_rotation_norm_rad",
    "full_solver_condition_number",
    "full_posterior_covariance_trace",
    "solver_failure",
]

GT_FIELDS = [
    "schema_version",
    *FRAME_KEY_FIELDS,
    "offline_evaluation_only",
    "gt_axis_world_x",
    "gt_axis_world_y",
    "gt_axis_world_z",
    "prior_axis_error_signed_m",
    "prior_axis_error_abs_m",
    "posterior_axis_error_signed_m",
    "posterior_axis_error_abs_m",
    "axis_abs_error_change_m",
    "axis_abs_error_reduction_m",
    "prior_online_weak_error_signed_m",
    "posterior_online_weak_error_signed_m",
    "online_weak_abs_error_reduction_m",
]

FORBIDDEN_ONLINE_FIELD_TOKENS = (
    "gt",
    "oracle",
    "axis_per_frame",
    "pose_gt",
    "error_prior",
    "error_posterior",
)

_DIRECTION_COMPONENTS = [
    "weak_direction_raw_world_x",
    "weak_direction_raw_world_y",
    "weak_direction_raw_world_z",
    "weak_direction_logged_world_x",
    "weak_direction_logged_world_y",
    "weak_direction_logged_world_z",
]

_DIRECTION_DEPENDENT_SCALARS = [
    "weak_score_gradient_raw",
    "weak_score_information_raw",
    "weak_innovation_z_raw",
    "weak_score_gradient_huber",
    "weak_score_information_huber",
    "weak_innovation_z_huber",
    "full_update_weak_signed_m",
    "full_update_weak_abs_m",
    "full_update_strong_x",
    "full_update_strong_y",
    "full_update_strong_z",
    "full_update_strong_norm_m",
    "applied_update_weak_signed_m",
    "applied_update_weak_abs_m",
    "applied_update_strong_x",
    "applied_update_strong_y",
    "applied_update_strong_z",
    "applied_update_strong_norm_m",
]


def validate_online_frame_record(record: Mapping[str, Any]) -> None:
    """Validate one online-only record without accepting offline GT fields."""

    _require_exact_schema(record, ONLINE_FIELDS, ONLINE_SCHEMA_VERSION)
    for name in record:
        lowered = name.lower()
        tokens = set(lowered.replace("-", "_").split("_"))
        if "gt" in tokens or "oracle" in tokens:
            raise ValueError(f"online record contains forbidden field: {name}")
        if any(token in lowered for token in FORBIDDEN_ONLINE_FIELD_TOKENS[2:]):
            raise ValueError(f"online record contains forbidden field: {name}")
    _validate_frame_key(record)
    _require_bool_fields(
        record,
        [
            "weak_direction_valid",
            "weak_direction_sign_flipped",
            "primary_direction_stable",
            "degeneracy_triggered",
            "actionable_direction",
            "weak_innovation_valid",
            "solver_failure",
        ],
    )
    _require_finite(record, ["odi_trans", "primary_eigengap_ratio"])
    if int(record["residual_count"]) <= 0:
        raise ValueError("residual_count must be positive")
    outliers = int(record["huber_outlier_count"])
    if not 0 <= outliers <= int(record["residual_count"]):
        raise ValueError("huber_outlier_count is outside the residual count")
    ratio = float(record["huber_outlier_ratio"])
    if not 0.0 <= ratio <= 1.0:
        raise ValueError("huber_outlier_ratio must be in [0, 1]")
    for name in ["mean_huber_weight", "min_huber_weight"]:
        value = float(record[name])
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be in (0, 1]")

    _require_finite(
        record,
        [
            "full_delta_theta_x",
            "full_delta_theta_y",
            "full_delta_theta_z",
            "full_delta_p_x",
            "full_delta_p_y",
            "full_delta_p_z",
            "full_update_rotation_norm_rad",
            "applied_delta_theta_x",
            "applied_delta_theta_y",
            "applied_delta_theta_z",
            "applied_delta_p_x",
            "applied_delta_p_y",
            "applied_delta_p_z",
            "applied_update_rotation_norm_rad",
        ],
    )

    if bool(record["solver_failure"]):
        if not math.isnan(float(record["full_posterior_covariance_trace"])):
            raise ValueError("failed full solve must mark its posterior trace as NaN")
    else:
        _require_finite(record, ["full_solver_condition_number", "full_posterior_covariance_trace"])
        if float(record["full_solver_condition_number"]) < 0.0:
            raise ValueError("solver condition number cannot be negative")
        if float(record["full_posterior_covariance_trace"]) < 0.0:
            raise ValueError("posterior covariance trace cannot be negative")

    if bool(record["weak_direction_valid"]):
        raw = np.asarray([record[name] for name in _DIRECTION_COMPONENTS[:3]], dtype=float)
        logged = np.asarray([record[name] for name in _DIRECTION_COMPONENTS[3:]], dtype=float)
        if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(logged)):
            raise ValueError("valid weak directions must be finite")
        if abs(float(np.linalg.norm(raw)) - 1.0) >= 1.0e-10:
            raise ValueError("raw weak direction is not unit length")
        if abs(float(np.linalg.norm(logged)) - 1.0) >= 1.0e-10:
            raise ValueError("logged weak direction is not unit length")
        projection_names = [
            name
            for name in _DIRECTION_DEPENDENT_SCALARS
            if "innovation_z" not in name
        ]
        _require_finite(record, projection_names)
        if bool(record["weak_innovation_valid"]):
            _require_finite(record, ["weak_innovation_z_raw", "weak_innovation_z_huber"])
        else:
            _require_nan(record, ["weak_innovation_z_raw", "weak_innovation_z_huber"])
    else:
        if bool(record["weak_direction_sign_flipped"]):
            raise ValueError("an invalid direction cannot be sign-flipped")
        if bool(record["weak_innovation_valid"]):
            raise ValueError("an invalid direction cannot have a valid innovation")
        _require_nan(record, _DIRECTION_COMPONENTS + _DIRECTION_DEPENDENT_SCALARS)


def validate_gt_frame_record(record: Mapping[str, Any]) -> None:
    """Validate one offline-only GT evaluation record."""

    _require_exact_schema(record, GT_FIELDS, GT_SCHEMA_VERSION)
    _validate_frame_key(record)
    if record["offline_evaluation_only"] is not True:
        raise ValueError("GT records must be marked offline_evaluation_only=true")
    axis = np.asarray(
        [record["gt_axis_world_x"], record["gt_axis_world_y"], record["gt_axis_world_z"]],
        dtype=float,
    )
    if not np.all(np.isfinite(axis)) or abs(float(np.linalg.norm(axis)) - 1.0) >= 1.0e-10:
        raise ValueError("GT axis must be finite and unit length")
    _require_finite(
        record,
        [
            "prior_axis_error_signed_m",
            "prior_axis_error_abs_m",
            "posterior_axis_error_signed_m",
            "posterior_axis_error_abs_m",
            "axis_abs_error_change_m",
            "axis_abs_error_reduction_m",
        ],
    )
    change = float(record["axis_abs_error_change_m"])
    reduction = float(record["axis_abs_error_reduction_m"])
    if not math.isclose(change, -reduction, abs_tol=1.0e-12, rel_tol=0.0):
        raise ValueError("axis error change and reduction must be exact opposites")
    weak_values = [
        float(record["prior_online_weak_error_signed_m"]),
        float(record["posterior_online_weak_error_signed_m"]),
        float(record["online_weak_abs_error_reduction_m"]),
    ]
    if not (all(math.isfinite(value) for value in weak_values) or all(math.isnan(value) for value in weak_values)):
        raise ValueError("online weak GT metrics must be all finite or all NaN")


def write_online_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        validate_online_frame_record(row)
    _write_fixed_csv(path, rows, ONLINE_FIELDS)


def write_gt_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        validate_gt_frame_record(row)
    _write_fixed_csv(path, rows, GT_FIELDS)


def frame_key(record: Mapping[str, Any]) -> tuple:
    return tuple(record[name] for name in FRAME_KEY_FIELDS)


def _require_exact_schema(
    record: Mapping[str, Any], fields: Sequence[str], expected_version: str
) -> None:
    missing = [name for name in fields if name not in record]
    extra = [name for name in record if name not in fields]
    if missing or extra:
        raise ValueError(f"schema mismatch: missing={missing}, extra={extra}")
    if record["schema_version"] != expected_version:
        raise ValueError(f"unexpected schema version: {record['schema_version']}")


def _validate_frame_key(record: Mapping[str, Any]) -> None:
    for name in FRAME_KEY_FIELDS:
        if record[name] is None or (isinstance(record[name], str) and not record[name]):
            raise ValueError(f"frame key is missing: {name}")
    if int(record["frame_index"]) < 0 or not math.isfinite(float(record["timestamp"])):
        raise ValueError("frame index and timestamp must be valid")


def _require_bool_fields(record: Mapping[str, Any], names: Sequence[str]) -> None:
    for name in names:
        if not isinstance(record[name], (bool, np.bool_)):
            raise ValueError(f"{name} must be boolean")


def _require_finite(record: Mapping[str, Any], names: Sequence[str]) -> None:
    for name in names:
        if not math.isfinite(float(record[name])):
            raise ValueError(f"{name} must be finite")


def _require_nan(record: Mapping[str, Any], names: Sequence[str]) -> None:
    for name in names:
        if not math.isnan(float(record[name])):
            raise ValueError(f"{name} must be NaN")


def _write_fixed_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
