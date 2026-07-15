"""Fixed output schema for Stage 2 Day 9 causal window statistics."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eval.stage2_failure_schema import FRAME_KEY_FIELDS, ONLINE_SCHEMA_VERSION


WINDOW_SCHEMA_VERSION = "stage2_failure_window_v1"
RESET_REASONS = {
    "none",
    "invalid_direction",
    "invalid_innovation",
    "unstable_direction",
    "nonfinite_signal",
}

SIGNAL_INTEGER_SUFFIXES = [
    "positive_count",
    "negative_count",
    "zero_count",
    "current_sign",
    "current_same_sign_run_length",
    "max_same_sign_run_length",
]
SIGNAL_FLOAT_SUFFIXES = [
    "window_mean",
    "window_median",
    "window_energy",
    "dominant_sign_ratio",
    "lag1_autocorrelation",
    "skewness",
    "cusum_positive",
    "cusum_negative",
    "cusum_max",
    "cusum_signed",
]
RAW_STAT_FIELDS = [f"raw_{name}" for name in SIGNAL_FLOAT_SUFFIXES + SIGNAL_INTEGER_SUFFIXES]
HUBER_STAT_FIELDS = [f"huber_{name}" for name in SIGNAL_FLOAT_SUFFIXES + SIGNAL_INTEGER_SUFFIXES]

WINDOW_FIELDS = [
    "schema_version",
    "source_online_schema_version",
    *FRAME_KEY_FIELDS,
    "weak_direction_valid",
    "weak_innovation_valid",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
    "odi_trans",
    "primary_eigengap_ratio",
    "stat_input_valid",
    "stat_reset_reason",
    "window_size",
    "window_count",
    "window_ready",
    "consecutive_valid_count",
    "weak_innovation_z_raw",
    "weak_innovation_z_huber",
    *RAW_STAT_FIELDS,
    *HUBER_STAT_FIELDS,
]

FORBIDDEN_FIELD_TOKENS = {
    "gt",
    "oracle",
    "pose_gt",
    "axis_per_frame",
    "prior_axis_error",
    "posterior_axis_error",
    "error_reduction",
    "scene_label",
}


def validate_window_record(record: Mapping[str, Any]) -> None:
    missing = [name for name in WINDOW_FIELDS if name not in record]
    extra = [name for name in record if name not in WINDOW_FIELDS]
    if missing or extra:
        raise ValueError(f"window schema mismatch: missing={missing}, extra={extra}")
    if record["schema_version"] != WINDOW_SCHEMA_VERSION:
        raise ValueError("unexpected Day 9 window schema version")
    if record["source_online_schema_version"] != ONLINE_SCHEMA_VERSION:
        raise ValueError("unexpected source online schema version")
    for name in record:
        lowered = name.lower()
        tokens = set(lowered.replace("-", "_").split("_"))
        if "gt" in tokens or "oracle" in tokens:
            raise ValueError(f"window record contains forbidden field: {name}")
        if any(
            forbidden in lowered
            for forbidden in FORBIDDEN_FIELD_TOKENS
            if forbidden not in {"gt", "oracle"}
        ):
            raise ValueError(f"window record contains forbidden field: {name}")

    _validate_frame_key(record)
    _require_booleans(
        record,
        [
            "weak_direction_valid",
            "weak_innovation_valid",
            "primary_direction_stable",
            "degeneracy_triggered",
            "actionable_direction",
            "stat_input_valid",
            "window_ready",
        ],
    )
    _require_no_inf(record)
    _require_finite(record, ["odi_trans", "primary_eigengap_ratio"])
    reason = str(record["stat_reset_reason"])
    if reason not in RESET_REASONS:
        raise ValueError(f"unsupported stat_reset_reason: {reason}")
    window_size = int(record["window_size"])
    count = int(record["window_count"])
    consecutive = int(record["consecutive_valid_count"])
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    if not bool(record["stat_input_valid"]):
        if reason == "none":
            raise ValueError("an invalid statistic input requires a reset reason")
        if count != 0 or consecutive != 0 or bool(record["window_ready"]):
            raise ValueError("an invalid frame must expose a fully reset common state")
        for prefix in ["raw", "huber"]:
            _validate_invalid_signal(record, prefix)
        return

    if reason != "none":
        raise ValueError("a valid statistic input must use reset reason 'none'")
    _require_finite(
        record,
        ["weak_innovation_z_raw", "weak_innovation_z_huber"],
    )
    if not 1 <= count <= window_size:
        raise ValueError("window_count is outside [1, window_size]")
    if consecutive < count:
        raise ValueError("consecutive_valid_count cannot be smaller than window_count")
    if bool(record["window_ready"]) != (count == window_size):
        raise ValueError("window_ready does not match window_count")
    for prefix in ["raw", "huber"]:
        _validate_valid_signal(record, prefix, count)


def write_window_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    for row in rows:
        validate_window_record(row)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WINDOW_FIELDS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def window_frame_key(record: Mapping[str, Any]) -> tuple:
    return tuple(record[name] for name in FRAME_KEY_FIELDS)


def _validate_invalid_signal(record: Mapping[str, Any], prefix: str) -> None:
    for suffix in SIGNAL_FLOAT_SUFFIXES:
        if not math.isnan(float(record[f"{prefix}_{suffix}"])):
            raise ValueError(f"invalid frame {prefix}_{suffix} must be NaN")
    for suffix in SIGNAL_INTEGER_SUFFIXES:
        if int(record[f"{prefix}_{suffix}"]) != 0:
            raise ValueError(f"invalid frame {prefix}_{suffix} must be zero")


def _validate_valid_signal(
    record: Mapping[str, Any],
    prefix: str,
    window_count: int,
) -> None:
    always_finite = [
        "window_mean",
        "window_median",
        "window_energy",
        "cusum_positive",
        "cusum_negative",
        "cusum_max",
        "cusum_signed",
    ]
    _require_finite(record, [f"{prefix}_{name}" for name in always_finite])
    if float(record[f"{prefix}_window_energy"]) < 0.0:
        raise ValueError("window energy cannot be negative")
    for suffix in ["lag1_autocorrelation", "skewness"]:
        value = float(record[f"{prefix}_{suffix}"])
        if math.isinf(value):
            raise ValueError(f"{prefix}_{suffix} cannot be infinite")

    positive = int(record[f"{prefix}_positive_count"])
    negative = int(record[f"{prefix}_negative_count"])
    zero = int(record[f"{prefix}_zero_count"])
    if min(positive, negative, zero) < 0:
        raise ValueError("sign counts cannot be negative")
    if positive + negative + zero != window_count:
        raise ValueError("sign counts must sum to window_count")
    current_sign = int(record[f"{prefix}_current_sign"])
    current_run = int(record[f"{prefix}_current_same_sign_run_length"])
    maximum_run = int(record[f"{prefix}_max_same_sign_run_length"])
    if current_sign not in {-1, 0, 1}:
        raise ValueError("current sign must be -1, 0, or +1")
    if not 0 <= current_run <= maximum_run <= window_count:
        raise ValueError("same-sign run lengths are outside the current window")
    if current_sign == 0 and current_run != 0:
        raise ValueError("zero current sign must have a zero current run")
    if current_sign != 0 and current_run < 1:
        raise ValueError("nonzero current sign must have a positive current run")

    ratio = float(record[f"{prefix}_dominant_sign_ratio"])
    if positive + negative == 0:
        if not math.isnan(ratio):
            raise ValueError("all-zero window dominant sign ratio must be NaN")
    elif not math.isfinite(ratio) or not 0.5 <= ratio <= 1.0:
        raise ValueError("dominant sign ratio must lie in [0.5, 1.0]")


def _validate_frame_key(record: Mapping[str, Any]) -> None:
    for name in FRAME_KEY_FIELDS:
        value = record[name]
        if value is None or (isinstance(value, str) and not value):
            raise ValueError(f"frame key is missing: {name}")
    if int(record["frame_index"]) < 0:
        raise ValueError("frame_index cannot be negative")
    if not math.isfinite(float(record["timestamp"])):
        raise ValueError("timestamp must be finite")


def _require_booleans(record: Mapping[str, Any], names: Sequence[str]) -> None:
    for name in names:
        if not isinstance(record[name], (bool, np.bool_)):
            raise ValueError(f"{name} must be boolean")


def _require_finite(record: Mapping[str, Any], names: Sequence[str]) -> None:
    for name in names:
        if not math.isfinite(float(record[name])):
            raise ValueError(f"{name} must be finite")


def _require_no_inf(record: Mapping[str, Any]) -> None:
    for name, raw in record.items():
        if isinstance(raw, (bool, np.bool_)) or not isinstance(
            raw, (int, float, np.integer, np.floating)
        ):
            continue
        if math.isinf(float(raw)):
            raise ValueError(f"{name} cannot be infinite")
