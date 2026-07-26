"""Recovery probabilities, Wilson intervals, decreasing PAVA, and radii."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Sequence

import numpy as np

from .types import DirectionRecoveryCurve


def _canonical_direction(value: Sequence[float] | np.ndarray) -> np.ndarray:
    direction = np.asarray(value, dtype=np.float64)
    if direction.shape != (3,) or not np.all(np.isfinite(direction)):
        raise ValueError("direction must be a finite length-3 vector")
    norm = float(np.linalg.norm(direction))
    if norm <= 1.0e-12:
        raise ValueError("direction cannot be zero")
    direction = direction / norm
    nonzero = np.flatnonzero(np.abs(direction) > 1.0e-12)
    if nonzero.size and float(direction[int(nonzero[0])]) < 0.0:
        direction = -direction
    return direction


def wilson_interval(
    successful_trials: int,
    total_trials: int,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    successes = int(successful_trials)
    total = int(total_trials)
    confidence = float(confidence_level)
    if successes != successful_trials or total != total_trials:
        raise ValueError("Wilson counts must be integers")
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson counts require 0 <= successes <= total and total > 0")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence_level must lie strictly between zero and one")
    z = NormalDist().inv_cdf(0.5 + 0.5 * confidence)
    probability = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (probability + z2 / (2.0 * total)) / denominator
    half_width = (
        z
        * math.sqrt(
            probability * (1.0 - probability) / total + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def wilson_intervals(
    successful_trials: Sequence[int] | np.ndarray,
    total_trials: Sequence[int] | np.ndarray,
    confidence_level: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    successes = np.asarray(successful_trials)
    totals = np.asarray(total_trials)
    if successes.shape != totals.shape or successes.ndim != 1:
        raise ValueError("success and total counts must be equal-length vectors")
    bounds = [
        wilson_interval(success, total, confidence_level)
        for success, total in zip(successes.tolist(), totals.tolist())
    ]
    return (
        np.asarray([bound[0] for bound in bounds], dtype=np.float64),
        np.asarray([bound[1] for bound in bounds], dtype=np.float64),
    )


def fit_nonincreasing_isotonic(
    probabilities: Sequence[float] | np.ndarray,
    weights: Sequence[float] | np.ndarray | None = None,
) -> np.ndarray:
    """Weighted decreasing PAVA without changing the supplied raw curve."""

    raw = np.asarray(probabilities, dtype=np.float64)
    if raw.ndim != 1 or raw.size == 0 or not np.all(np.isfinite(raw)):
        raise ValueError("probabilities must be a non-empty finite vector")
    if np.any((raw < 0.0) | (raw > 1.0)):
        raise ValueError("probabilities must lie in [0,1]")
    if weights is None:
        weight_values = np.ones(raw.size, dtype=np.float64)
    else:
        weight_values = np.asarray(weights, dtype=np.float64)
        if weight_values.shape != raw.shape:
            raise ValueError("isotonic weights must match probabilities")
        if not np.all(np.isfinite(weight_values)) or np.any(weight_values <= 0.0):
            raise ValueError("isotonic weights must be finite and positive")

    # Each block is [start, stop, total_weight, weighted_probability_sum].
    blocks: list[list[float]] = []
    for index, (value, weight) in enumerate(zip(raw, weight_values)):
        blocks.append([float(index), float(index + 1), float(weight), float(weight * value)])
        while len(blocks) >= 2:
            previous = blocks[-2]
            current = blocks[-1]
            previous_mean = previous[3] / previous[2]
            current_mean = current[3] / current[2]
            if previous_mean >= current_mean:
                break
            merged = [
                previous[0],
                current[1],
                previous[2] + current[2],
                previous[3] + current[3],
            ]
            blocks[-2:] = [merged]

    fitted = np.empty(raw.size, dtype=np.float64)
    for start, stop, total_weight, weighted_sum in blocks:
        fitted[int(start) : int(stop)] = weighted_sum / total_weight
    return fitted


def capture_radius_from_fitted(
    amplitudes: Sequence[float] | np.ndarray,
    fitted_probabilities: Sequence[float] | np.ndarray,
    target_probability: float,
) -> tuple[float | None, bool]:
    """Return the first sampled amplitude with fitted P <= target.

    The Day 1 MVP is deliberately discrete.  If no sampled probability reaches
    the target, the radius is right-censored and no value is extrapolated.
    """

    values = np.asarray(amplitudes, dtype=np.float64)
    probabilities = np.asarray(fitted_probabilities, dtype=np.float64)
    target = float(target_probability)
    if values.ndim != 1 or values.size == 0 or probabilities.shape != values.shape:
        raise ValueError("amplitudes and fitted probabilities must be equal-length vectors")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(np.diff(values) < 0.0):
        raise ValueError("amplitudes must be finite, non-negative, and sorted")
    if not np.all(np.isfinite(probabilities)) or np.any(
        (probabilities < 0.0) | (probabilities > 1.0)
    ):
        raise ValueError("fitted probabilities must lie in [0,1]")
    if np.any(np.diff(probabilities) > 1.0e-12):
        raise ValueError("fitted probabilities must be non-increasing")
    if not 0.0 < target < 1.0:
        raise ValueError("target_probability must lie strictly between zero and one")
    reached = np.flatnonzero(probabilities <= target)
    if reached.size == 0:
        return None, True
    return float(values[int(reached[0])]), False


def build_direction_recovery_curve(
    *,
    direction_id: str,
    direction: Sequence[float] | np.ndarray,
    signed_side: int,
    amplitudes: Sequence[float] | np.ndarray,
    successful_trials: Sequence[int] | np.ndarray,
    total_trials: Sequence[int] | np.ndarray,
    confidence_level: float = 0.95,
    snapshot_id: str = "",
    perturbation_type: str = "",
    registration_path: str = "full_reassociation",
    full_reassociation: bool = True,
    baseline_only: bool = False,
) -> DirectionRecoveryCurve:
    amplitudes_array = np.asarray(amplitudes, dtype=np.float64)
    successes = np.asarray(successful_trials)
    totals = np.asarray(total_trials)
    if successes.shape != amplitudes_array.shape or totals.shape != amplitudes_array.shape:
        raise ValueError("trial-count arrays must match amplitudes")
    if amplitudes_array.ndim != 1 or amplitudes_array.size == 0:
        raise ValueError("amplitudes must be a non-empty vector")
    if np.any(np.diff(amplitudes_array) < 0.0):
        raise ValueError("amplitudes must be sorted")
    if np.any(totals <= 0) or np.any(successes < 0) or np.any(successes > totals):
        raise ValueError("trial counts require 0 <= successes <= totals and totals > 0")
    raw = successes.astype(np.float64) / totals.astype(np.float64)
    fitted = fit_nonincreasing_isotonic(raw, totals.astype(np.float64))
    lower, upper = wilson_intervals(successes, totals, confidence_level)
    d50, d50_censored = capture_radius_from_fitted(amplitudes_array, fitted, 0.5)
    d90, d90_censored = capture_radius_from_fitted(amplitudes_array, fitted, 0.9)
    return DirectionRecoveryCurve(
        direction_id=str(direction_id),
        # Curves expose the physical signed direction, while perturbation specs
        # retain a canonical basis and carry sign only in signed_amplitude.
        direction=float(signed_side) * _canonical_direction(direction),
        signed_side=int(signed_side),
        amplitudes=amplitudes_array,
        raw_probabilities=raw,
        fitted_probabilities=fitted,
        wilson_lower=lower,
        wilson_upper=upper,
        d50=d50,
        d90=d90,
        d50_right_censored=d50_censored,
        d90_right_censored=d90_censored,
        snapshot_id=str(snapshot_id),
        perturbation_type=str(perturbation_type),
        registration_path=str(registration_path),
        full_reassociation=bool(full_reassociation),
        baseline_only=bool(baseline_only),
    )
