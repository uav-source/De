"""Timestamp and future-error helpers for the Measurement scientific audit."""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


def validate_strict_seconds_timestamps(timestamps: Sequence[float]) -> np.ndarray:
    """Validate Unix epoch timestamps expressed in seconds.

    The MUN-FRL lock uses message-header Unix seconds.  Large microsecond or
    nanosecond integers are rejected instead of silently producing a plausible
    ordering with the wrong unit.
    """

    values = np.asarray(timestamps, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("timestamps must be a one-dimensional sequence of length >= 2")
    if not np.all(np.isfinite(values)):
        raise ValueError("timestamps must be finite")
    if float(np.max(np.abs(values))) >= 1.0e12:
        raise ValueError("timestamps look like microseconds or nanoseconds, not seconds")
    if float(np.min(values)) < 1.0e8:
        raise ValueError("timestamps do not match the frozen Unix-seconds clock")
    if np.any(np.diff(values) <= 0.0):
        raise ValueError("timestamps must be strictly increasing without duplicates")
    return values


def time_stream_summary(
    stream: str,
    timestamps: Sequence[float],
    *,
    timestamp_source: str,
    applied_offset_seconds: float = 0.0,
) -> dict[str, Any]:
    values = np.asarray(timestamps, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError(f"{stream} has no finite timestamps")
    deltas = np.diff(finite)
    positive = deltas[deltas > 0.0]
    return {
        "stream": stream,
        "timestamp_source": timestamp_source,
        "unit": "seconds",
        "applied_offset_seconds": float(applied_offset_seconds),
        "start_time": float(finite[0]),
        "end_time": float(finite[-1]),
        "sample_count": int(finite.size),
        "median_period_seconds": float(np.median(positive)) if positive.size else float("nan"),
        "q05_period_seconds": float(np.quantile(positive, 0.05)) if positive.size else float("nan"),
        "q95_period_seconds": float(np.quantile(positive, 0.95)) if positive.size else float("nan"),
        "duplicate_timestamp_count": int(np.sum(deltas == 0.0)),
        "non_monotonic_count": int(np.sum(deltas < 0.0)),
    }


def _validate_trajectory(
    timestamps: Sequence[float],
    estimated_positions: np.ndarray,
    reference_positions: np.ndarray,
    window_seconds: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    times = np.asarray(timestamps, dtype=np.float64)
    estimated = np.asarray(estimated_positions, dtype=np.float64)
    reference = np.asarray(reference_positions, dtype=np.float64)
    if times.ndim != 1 or estimated.shape != (times.size, 3) or reference.shape != estimated.shape:
        raise ValueError("trajectory inputs must be timestamp N and two N x 3 arrays")
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(estimated)) or not np.all(np.isfinite(reference)):
        raise ValueError("future-error inputs must be finite")
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("future-error timestamps must be strictly increasing")
    if not math.isfinite(float(window_seconds)) or float(window_seconds) <= 0.0:
        raise ValueError("future-error window must be finite and positive")
    return times, estimated, reference


def _interpolate_positions(
    timestamps: np.ndarray, positions: np.ndarray, queries: np.ndarray
) -> np.ndarray:
    return np.column_stack(
        [np.interp(queries, timestamps, positions[:, axis]) for axis in range(3)]
    )


def exact_future_error_growth(
    timestamps: Sequence[float],
    estimated_positions: np.ndarray,
    reference_positions: np.ndarray,
    *,
    window_seconds: float = 5.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return e(t + window) - e(t) at the exact future timestamps.

    Both aligned estimator and reference position vectors are linearly
    interpolated before their Euclidean error is evaluated.
    """

    times, estimated, reference = _validate_trajectory(
        timestamps, estimated_positions, reference_positions, window_seconds
    )
    target = times + float(window_seconds)
    available = target <= times[-1]
    growth = np.full(times.size, np.nan, dtype=np.float64)
    if np.any(available):
        estimated_future = _interpolate_positions(times, estimated, target[available])
        reference_future = _interpolate_positions(times, reference, target[available])
        current_error = np.linalg.norm(estimated[available] - reference[available], axis=1)
        future_error = np.linalg.norm(estimated_future - reference_future, axis=1)
        growth[available] = future_error - current_error
    return growth, available


def discrete_future_error_growth(
    timestamps: Sequence[float],
    estimated_positions: np.ndarray,
    reference_positions: np.ndarray,
    *,
    window_seconds: float = 5.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reproduce the original first-sample-at-or-after-window definition."""

    times, estimated, reference = _validate_trajectory(
        timestamps, estimated_positions, reference_positions, window_seconds
    )
    error = np.linalg.norm(estimated - reference, axis=1)
    indices = np.searchsorted(times, times + float(window_seconds))
    available = indices < times.size
    growth = np.full(times.size, np.nan, dtype=np.float64)
    horizon = np.full(times.size, np.nan, dtype=np.float64)
    source = np.flatnonzero(available)
    growth[available] = error[indices[available]] - error[available]
    horizon[available] = times[indices[available]] - times[source]
    return growth, available, horizon
