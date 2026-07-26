"""Continuity summaries for Day 6 Fallback shadow-detector outputs."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from .day6_fallback_functional_diagnostics import FLAG_FIELDS


class ContinuityError(ValueError):
    """Raised when a detector output stream is incomplete or out of order."""


def sign_invariant_angle_deg(
    left: Sequence[float], right: Sequence[float]
) -> float:
    u = np.asarray(left, dtype=np.float64)
    v = np.asarray(right, dtype=np.float64)
    if u.shape != (3,) or v.shape != (3,):
        raise ContinuityError("direction vectors must have shape (3,)")
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(v)):
        raise ContinuityError("direction vectors must be finite")
    unorm = float(np.linalg.norm(u))
    vnorm = float(np.linalg.norm(v))
    if unorm <= 0.0 or vnorm <= 0.0:
        raise ContinuityError("direction vectors must have positive norm")
    cosine = float(np.clip(abs(np.dot(u / unorm, v / vnorm)), 0.0, 1.0))
    return math.degrees(math.acos(cosine))


def _quantile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def output_continuity(
    observations: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observation_keys = [
        (
            int(row["scan_index"]),
            float(row["timestamp_begin"]),
            float(row["timestamp_end"]),
        )
        for row in observations
    ]
    output_keys = [
        (
            int(row["scan_index"]),
            float(row["timestamp_begin"]),
            float(row["timestamp_end"]),
        )
        for row in outputs
    ]
    missing = len(set(observation_keys) - set(output_keys))
    duplicates = len(output_keys) - len(set(output_keys))
    backward = sum(
        right[1] < left[1] or right[2] < left[2]
        for left, right in zip(output_keys, output_keys[1:])
    )
    timestamp_duplicate = sum(
        right[1:] == left[1:]
        for left, right in zip(output_keys, output_keys[1:])
    )
    scan_gap = sum(
        right[0] != left[0] + 1
        for left, right in zip(output_keys, output_keys[1:])
    )
    duplicate_scan = len(output_keys) - len({row[0] for row in output_keys})
    identity_mismatch = sum(
        left != right for left, right in zip(observation_keys, output_keys)
    ) + abs(len(observation_keys) - len(output_keys))
    summary = {
        "schema_version": "day6_output_continuity_summary_v1",
        "output_record_count": len(outputs),
        "first_output_scan_index": output_keys[0][0] if output_keys else None,
        "last_output_scan_index": output_keys[-1][0] if output_keys else None,
        "timestamp_backward_count": backward,
        "timestamp_duplicate_count": timestamp_duplicate,
        "scan_index_gap_count": scan_gap,
        "duplicate_scan_index_count": duplicate_scan,
        "missing_output_count": missing,
        "duplicate_output_count": duplicates,
        "identity_mismatch_count": identity_mismatch,
        "consecutive_output_pair_count": max(0, len(outputs) - 1),
    }
    summary["output_timestamp_monotonicity_pass"] = backward == 0
    summary["output_continuity_diagnostics_pass"] = all(
        summary[name] == 0
        for name in (
            "timestamp_backward_count",
            "scan_index_gap_count",
            "duplicate_scan_index_count",
            "missing_output_count",
            "duplicate_output_count",
            "identity_mismatch_count",
        )
    )
    if not summary["output_continuity_diagnostics_pass"]:
        raise ContinuityError(f"output continuity failed: {summary}")
    return summary


def direction_continuity(
    outputs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible: list[Mapping[str, Any]] = []
    null_count = 0
    unstable_count = 0
    for row in outputs:
        direction = row.get("primary_weak_direction")
        if direction is None:
            null_count += 1
            continue
        if row.get("valid") is not True or row.get(
            "primary_direction_stable"
        ) is not True:
            unstable_count += 1
            continue
        try:
            vector = np.asarray(direction, dtype=np.float64)
            finite = vector.shape == (3,) and np.all(np.isfinite(vector))
            legal_norm = finite and float(np.linalg.norm(vector)) > 0.0
        except (TypeError, ValueError):
            legal_norm = False
        if not legal_norm:
            null_count += 1
            continue
        eligible.append(row)

    records: list[dict[str, Any]] = []
    angles: list[float] = []
    direction_gap_count = 0
    for left, right in zip(eligible, eligible[1:]):
        angle = sign_invariant_angle_deg(
            left["primary_weak_direction"],
            right["primary_weak_direction"],
        )
        scan_gap = int(right["scan_index"]) - int(left["scan_index"]) - 1
        direction_gap_count += int(scan_gap > 0)
        angles.append(angle)
        records.append(
            {
                "previous_record_index": int(left["record_index"]),
                "record_index": int(right["record_index"]),
                "previous_scan_index": int(left["scan_index"]),
                "scan_index": int(right["scan_index"]),
                "intervening_scan_count": max(0, scan_gap),
                "sign_invariant_angle_deg": angle,
            }
        )
    summary = {
        "schema_version": "day6_direction_continuity_summary_v1",
        "eligible_direction_record_count": len(eligible),
        "eligible_adjacent_pair_count": len(angles),
        "angle_min_deg": min(angles) if angles else None,
        "angle_median_deg": _quantile(angles, 50),
        "angle_p90_deg": _quantile(angles, 90),
        "angle_p95_deg": _quantile(angles, 95),
        "angle_p99_deg": _quantile(angles, 99),
        "angle_max_deg": max(angles) if angles else None,
        "direction_gap_count": direction_gap_count,
        "unstable_direction_count": unstable_count,
        "null_direction_count": null_count,
        "descriptive_only": True,
        "accuracy_threshold_applied": False,
        "direction_continuity_diagnostics_pass": True,
    }
    return records, summary


def _runs(values: Sequence[bool], target: bool) -> int:
    best = current = 0
    for value in values:
        if value is target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def flag_continuity(
    outputs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeline = [
        {
            "record_index": int(row["record_index"]),
            "scan_index": int(row["scan_index"]),
            **{field: bool(row[field]) for field in FLAG_FIELDS},
        }
        for row in outputs
    ]
    summaries: dict[str, Any] = {}
    for field in FLAG_FIELDS:
        values = [bool(row[field]) for row in outputs]
        false_to_true = sum(
            not left and right for left, right in zip(values, values[1:])
        )
        true_to_false = sum(
            left and not right for left, right in zip(values, values[1:])
        )
        true_count = sum(values)
        summaries[field] = {
            "true_count": true_count,
            "false_count": len(values) - true_count,
            "true_fraction": true_count / len(values) if values else None,
            "false_to_true_transition_count": false_to_true,
            "true_to_false_transition_count": true_to_false,
            "longest_true_run": _runs(values, True),
            "longest_false_run": _runs(values, False),
        }
    summary = {
        "schema_version": "day6_detector_flag_transition_summary_v1",
        "record_count": len(outputs),
        "flags": summaries,
        "degeneracy_triggered_is_ground_truth": False,
        "flag_continuity_diagnostics_pass": len(outputs) > 0,
    }
    return timeline, summary
