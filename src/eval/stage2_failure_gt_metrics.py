"""Offline ground-truth metrics for Stage 2 Day 8 frame diagnostics."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    GT_SCHEMA_VERSION,
    validate_gt_frame_record,
)


def evaluate_gt_frame_records(
    online_records: Sequence[Mapping[str, Any]],
    prior_poses: np.ndarray,
    posterior_poses: np.ndarray,
    pose_gt: np.ndarray,
    axis_per_frame: np.ndarray,
) -> Sequence[Mapping[str, Any]]:
    """Join online frame keys with offline prior/posterior axial errors."""

    priors = np.asarray(prior_poses, dtype=float)
    posteriors = np.asarray(posterior_poses, dtype=float)
    truth = np.asarray(pose_gt, dtype=float)
    axes = np.asarray(axis_per_frame, dtype=float)
    if priors.shape != posteriors.shape or priors.shape != truth.shape:
        raise ValueError("prior, posterior, and ground-truth poses must have equal shapes")
    if priors.ndim != 2 or priors.shape[1] != 8 or axes.shape != (priors.shape[0], 3):
        raise ValueError("offline evaluation expects poses [N,8] and axes [N,3]")
    if not all(np.all(np.isfinite(value)) for value in [priors, posteriors, truth, axes]):
        raise ValueError("offline evaluation inputs must be finite")

    output = []
    for online in online_records:
        frame = int(online["frame_index"])
        if not 0 <= frame < priors.shape[0]:
            raise ValueError("online frame index is outside the offline arrays")
        axis = _normalize(axes[frame], "ground-truth axis")
        prior_error = priors[frame, 1:4] - truth[frame, 1:4]
        posterior_error = posteriors[frame, 1:4] - truth[frame, 1:4]
        prior_axis_signed = float(axis @ prior_error)
        posterior_axis_signed = float(axis @ posterior_error)
        prior_axis_abs = abs(prior_axis_signed)
        posterior_axis_abs = abs(posterior_axis_signed)

        weak_metrics = [float("nan"), float("nan"), float("nan")]
        if bool(online["weak_direction_valid"]):
            weak = _normalize(
                np.asarray(
                    [
                        online["weak_direction_logged_world_x"],
                        online["weak_direction_logged_world_y"],
                        online["weak_direction_logged_world_z"],
                    ],
                    dtype=float,
                ),
                "logged online weak direction",
            )
            prior_weak = float(weak @ prior_error)
            posterior_weak = float(weak @ posterior_error)
            weak_metrics = [
                prior_weak,
                posterior_weak,
                abs(prior_weak) - abs(posterior_weak),
            ]

        record = {
            "schema_version": GT_SCHEMA_VERSION,
            **{name: online[name] for name in FRAME_KEY_FIELDS},
            "offline_evaluation_only": True,
            "gt_axis_world_x": float(axis[0]),
            "gt_axis_world_y": float(axis[1]),
            "gt_axis_world_z": float(axis[2]),
            "prior_axis_error_signed_m": prior_axis_signed,
            "prior_axis_error_abs_m": prior_axis_abs,
            "posterior_axis_error_signed_m": posterior_axis_signed,
            "posterior_axis_error_abs_m": posterior_axis_abs,
            "axis_abs_error_change_m": posterior_axis_abs - prior_axis_abs,
            "axis_abs_error_reduction_m": prior_axis_abs - posterior_axis_abs,
            "prior_online_weak_error_signed_m": weak_metrics[0],
            "posterior_online_weak_error_signed_m": weak_metrics[1],
            "online_weak_abs_error_reduction_m": weak_metrics[2],
        }
        validate_gt_frame_record(record)
        output.append(record)
    return tuple(output)


def _normalize(values: np.ndarray, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite length-3 vector")
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-12:
        raise ValueError(f"{name} cannot be zero")
    return vector / norm
