"""Online-only, read-only frame diagnostics for Stage 2 failure analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    ONLINE_SCHEMA_VERSION,
    validate_online_frame_record,
)
from minibench.update_strategies import RobustLinearSystem, make_translation_direction_6d


DIRECTIONAL_INFORMATION_EPSILON = 1.0e-12
_CONTEXT_FIELDS = FRAME_KEY_FIELDS[:-2]


@dataclass(frozen=True)
class DirectionalScore:
    gradient: float
    information: float
    z: float
    valid: bool


@dataclass(frozen=True)
class UpdateProjection:
    weak_signed: float
    weak_abs: float
    strong_vector: np.ndarray
    strong_norm: float
    rotation_norm: float


def orient_direction_for_logging(
    current_direction_world: np.ndarray,
    previous_valid_direction_world: Optional[np.ndarray],
) -> Tuple[np.ndarray, bool]:
    """Normalize and orient one direction without changing detector output."""

    current = _normalized_direction(current_direction_world)
    if previous_valid_direction_world is None:
        return current, False
    previous = _normalized_direction(previous_valid_direction_world)
    if float(current @ previous) < 0.0:
        return -current, True
    return current, False


def compute_directional_score(
    H: np.ndarray,
    b: np.ndarray,
    direction_world: np.ndarray,
    information_epsilon: float = DIRECTIONAL_INFORMATION_EPSILON,
) -> DirectionalScore:
    """Compute the signed directional score statistic (not a Kalman NIS)."""

    information_matrix = np.asarray(H, dtype=float)
    gradient_vector = np.asarray(b, dtype=float)
    if information_matrix.shape != (6, 6) or gradient_vector.shape != (6,):
        raise ValueError("directional score expects H [6,6] and b [6]")
    if not np.all(np.isfinite(information_matrix)) or not np.all(np.isfinite(gradient_vector)):
        raise ValueError("directional score inputs must be finite")
    if float(information_epsilon) < 0.0:
        raise ValueError("directional information epsilon must be non-negative")
    lifted = make_translation_direction_6d(direction_world)
    information = float(lifted @ information_matrix @ lifted)
    gradient = float(-lifted @ gradient_vector)
    valid = bool(information > float(information_epsilon))
    z = gradient / np.sqrt(information) if valid else float("nan")
    return DirectionalScore(
        gradient=gradient,
        information=information,
        z=float(z),
        valid=valid,
    )


def project_update(
    delta: np.ndarray,
    direction_world: np.ndarray,
) -> UpdateProjection:
    """Project a physical pose correction onto weak/strong translation modes."""

    correction = np.asarray(delta, dtype=float)
    if correction.shape != (6,) or not np.all(np.isfinite(correction)):
        raise ValueError("pose correction must be a finite length-6 vector")
    direction = _normalized_direction(direction_world)
    translation = correction[3:6]
    weak_signed = float(direction @ translation)
    strong = translation - direction * weak_signed
    return UpdateProjection(
        weak_signed=weak_signed,
        weak_abs=abs(weak_signed),
        strong_vector=strong,
        strong_norm=float(np.linalg.norm(strong)),
        rotation_norm=float(np.linalg.norm(correction[:3])),
    )


class Stage2FailureOnlineLogger:
    """Per-run online logger with local-only direction sign continuity state."""

    def __init__(
        self,
        context: Mapping[str, Any],
        directional_information_epsilon: float = DIRECTIONAL_INFORMATION_EPSILON,
    ) -> None:
        missing = [name for name in _CONTEXT_FIELDS if name not in context]
        extra = [name for name in context if name not in _CONTEXT_FIELDS]
        if missing or extra:
            raise ValueError(f"online logging context mismatch: missing={missing}, extra={extra}")
        self._context = {name: context[name] for name in _CONTEXT_FIELDS}
        self._epsilon = float(directional_information_epsilon)
        if self._epsilon != DIRECTIONAL_INFORMATION_EPSILON:
            raise ValueError("Day 8 directional information epsilon is frozen at 1.0e-12")
        self._previous_valid_direction: Optional[np.ndarray] = None
        self._records = []

    @property
    def records(self) -> Sequence[Mapping[str, Any]]:
        return tuple(dict(record) for record in self._records)

    def log_frame(
        self,
        *,
        frame_index: int,
        timestamp: float,
        jacobian: np.ndarray,
        residual: np.ndarray,
        variance: np.ndarray,
        robust_system: RobustLinearSystem,
        detected_direction_world: np.ndarray,
        direction_reliable: bool,
        detector_metrics: Mapping[str, Any],
        full_delta: np.ndarray,
        full_solver_condition_number: float,
        full_posterior_covariance_trace: float,
        applied_delta: np.ndarray,
        applied_strategy: str,
        solver_failure: bool,
    ) -> Mapping[str, Any]:
        """Build and retain one record using only current-frame online values."""

        J = np.asarray(jacobian, dtype=float).copy()
        values = np.asarray(residual, dtype=float).copy()
        variances = np.asarray(variance, dtype=float).copy()
        full = np.asarray(full_delta, dtype=float).copy()
        applied = np.asarray(applied_delta, dtype=float).copy()
        if J.ndim != 2 or J.shape[1] != 6 or values.shape != (J.shape[0],):
            raise ValueError("online logger expects J [N,6] and residual [N]")
        if variances.shape != values.shape or np.any(variances <= 0.0):
            raise ValueError("online logger variances must be positive and match residual")
        if not all(np.all(np.isfinite(item)) for item in [J, values, variances, full, applied]):
            raise ValueError("online logger inputs must be finite")

        weights = np.asarray(robust_system.robust_weights, dtype=float).copy()
        if weights.shape != values.shape or not np.all(np.isfinite(weights)):
            raise ValueError("robust weights must match residuals and be finite")
        if np.any(weights <= 0.0) or np.any(weights > 1.0):
            raise ValueError("robust weights must lie in (0, 1]")

        direction_valid = _direction_is_valid(detected_direction_world, direction_reliable)
        raw_direction = np.full(3, np.nan, dtype=float)
        logged_direction = np.full(3, np.nan, dtype=float)
        sign_flipped = False
        nan_score = DirectionalScore(float("nan"), float("nan"), float("nan"), False)
        raw_score = nan_score
        huber_score = nan_score
        full_projection = None
        applied_projection = None
        if direction_valid:
            raw_direction = _normalized_direction(detected_direction_world)
            logged_direction, sign_flipped = orient_direction_for_logging(
                raw_direction,
                self._previous_valid_direction,
            )
            precision = 1.0 / variances
            raw_H = (J * precision[:, None]).T @ J
            raw_b = J.T @ (precision * values)
            raw_score = compute_directional_score(raw_H, raw_b, logged_direction, self._epsilon)
            huber_score = compute_directional_score(
                robust_system.H,
                robust_system.b,
                logged_direction,
                self._epsilon,
            )
            full_projection = project_update(full, logged_direction)
            applied_projection = project_update(applied, logged_direction)
            self._previous_valid_direction = logged_direction.copy()

        innovation_valid = bool(direction_valid and raw_score.valid and huber_score.valid)
        raw_z = raw_score.z if innovation_valid else float("nan")
        huber_z = huber_score.z if innovation_valid else float("nan")
        record = {
            "schema_version": ONLINE_SCHEMA_VERSION,
            **self._context,
            "frame_index": int(frame_index),
            "timestamp": float(timestamp),
            "weak_direction_valid": bool(direction_valid),
            "weak_direction_raw_world_x": float(raw_direction[0]),
            "weak_direction_raw_world_y": float(raw_direction[1]),
            "weak_direction_raw_world_z": float(raw_direction[2]),
            "weak_direction_logged_world_x": float(logged_direction[0]),
            "weak_direction_logged_world_y": float(logged_direction[1]),
            "weak_direction_logged_world_z": float(logged_direction[2]),
            "weak_direction_sign_flipped": bool(sign_flipped),
            "odi_trans": float(detector_metrics["ODI_trans"]),
            "primary_eigengap_ratio": float(detector_metrics["primary_eigengap_ratio"]),
            "primary_direction_stable": bool(detector_metrics["primary_direction_stable"]),
            "degeneracy_triggered": bool(detector_metrics["degeneracy_triggered"]),
            "actionable_direction": bool(detector_metrics["actionable_direction"]),
            "weak_innovation_valid": innovation_valid,
            "weak_score_gradient_raw": raw_score.gradient,
            "weak_score_information_raw": raw_score.information,
            "weak_innovation_z_raw": raw_z,
            "weak_score_gradient_huber": huber_score.gradient,
            "weak_score_information_huber": huber_score.information,
            "weak_innovation_z_huber": huber_z,
            "residual_count": int(values.size),
            "huber_outlier_count": int(np.count_nonzero(weights < 1.0)),
            "huber_outlier_ratio": float(np.mean(weights < 1.0)),
            "mean_huber_weight": float(np.mean(weights)),
            "min_huber_weight": float(np.min(weights)),
            "full_delta_theta_x": float(full[0]),
            "full_delta_theta_y": float(full[1]),
            "full_delta_theta_z": float(full[2]),
            "full_delta_p_x": float(full[3]),
            "full_delta_p_y": float(full[4]),
            "full_delta_p_z": float(full[5]),
            **_projection_fields("full", full_projection, full),
            "applied_strategy": str(applied_strategy),
            "applied_delta_theta_x": float(applied[0]),
            "applied_delta_theta_y": float(applied[1]),
            "applied_delta_theta_z": float(applied[2]),
            "applied_delta_p_x": float(applied[3]),
            "applied_delta_p_y": float(applied[4]),
            "applied_delta_p_z": float(applied[5]),
            **_projection_fields("applied", applied_projection, applied),
            "full_solver_condition_number": float(full_solver_condition_number),
            "full_posterior_covariance_trace": float(full_posterior_covariance_trace),
            "solver_failure": bool(solver_failure),
        }
        validate_online_frame_record(record)
        self._records.append(dict(record))
        return dict(record)


def _projection_fields(
    prefix: str,
    projection: Optional[UpdateProjection],
    delta: np.ndarray,
) -> Mapping[str, float]:
    if projection is None:
        values = [float("nan")] * 6
        rotation_norm = float(np.linalg.norm(np.asarray(delta, dtype=float)[:3]))
    else:
        values = [
            projection.weak_signed,
            projection.weak_abs,
            float(projection.strong_vector[0]),
            float(projection.strong_vector[1]),
            float(projection.strong_vector[2]),
            projection.strong_norm,
        ]
        rotation_norm = projection.rotation_norm
    return {
        f"{prefix}_update_weak_signed_m": values[0],
        f"{prefix}_update_weak_abs_m": values[1],
        f"{prefix}_update_strong_x": values[2],
        f"{prefix}_update_strong_y": values[3],
        f"{prefix}_update_strong_z": values[4],
        f"{prefix}_update_strong_norm_m": values[5],
        f"{prefix}_update_rotation_norm_rad": rotation_norm,
    }


def _direction_is_valid(direction: np.ndarray, reliable: bool) -> bool:
    value = np.asarray(direction, dtype=float)
    return bool(
        reliable
        and value.shape == (3,)
        and np.all(np.isfinite(value))
        and float(np.linalg.norm(value)) > 1.0e-12
    )


def _normalized_direction(direction: np.ndarray) -> np.ndarray:
    value = np.asarray(direction, dtype=float)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise ValueError("direction must be a finite length-3 vector")
    norm = float(np.linalg.norm(value))
    if norm <= 1.0e-12:
        raise ValueError("direction cannot be zero")
    return value / norm
