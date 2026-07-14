"""Covariance-aware robust MAP update strategies for Stage 2B."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class NormalEquation:
    H: np.ndarray
    b: np.ndarray
    robust_weights: np.ndarray


@dataclass(frozen=True)
class UpdateResult:
    delta: np.ndarray
    posterior_covariance: np.ndarray
    effective_H: np.ndarray
    effective_b: np.ndarray
    strategy: str
    degeneracy_triggered: bool
    actionable_direction: bool
    attenuation_alpha: float
    solver_condition_number: float


def huber_weights(
    residual: np.ndarray,
    variance: np.ndarray,
    delta_sigma: float,
) -> np.ndarray:
    values = np.asarray(residual, dtype=float)
    variances = np.asarray(variance, dtype=float)
    if values.shape != variances.shape or values.ndim != 1:
        raise ValueError("residual and variance must be equal-length vectors")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(variances)):
        raise ValueError("Huber inputs must be finite")
    if np.any(variances <= 0.0) or float(delta_sigma) <= 0.0:
        raise ValueError("variance and Huber threshold must be positive")
    standardized = np.abs(values) / np.sqrt(variances)
    weights = np.ones_like(standardized)
    outside = standardized > float(delta_sigma)
    weights[outside] = float(delta_sigma) / standardized[outside]
    return weights


def build_normal_equation(
    J: np.ndarray,
    residual: np.ndarray,
    variance: np.ndarray,
    huber_delta_sigma: float,
) -> NormalEquation:
    jacobian = np.asarray(J, dtype=float)
    values = np.asarray(residual, dtype=float)
    variances = np.asarray(variance, dtype=float)
    if jacobian.ndim != 2 or jacobian.shape[1] != 6 or jacobian.shape[0] != values.size:
        raise ValueError("J must have shape [N, 6] and match residual")
    robust = huber_weights(values, variances, huber_delta_sigma)
    precision = robust / variances
    H = jacobian.T @ (jacobian * precision[:, None])
    b = jacobian.T @ (values * precision)
    H = _project_psd_roundoff(H, "Huber information")
    return NormalEquation(H=H, b=b, robust_weights=robust)


def solve_map_update(
    prior_covariance: np.ndarray,
    effective_H: np.ndarray,
    effective_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    covariance = _validated_psd(prior_covariance, "prior covariance", positive_definite=True)
    H = _validated_psd(effective_H, "effective information", positive_definite=False)
    b = np.asarray(effective_b, dtype=float)
    if b.shape != (6,) or not np.all(np.isfinite(b)):
        raise ValueError("effective_b must be a finite length-6 vector")
    try:
        prior_information = np.linalg.solve(covariance, np.eye(6))
    except np.linalg.LinAlgError as error:
        raise RuntimeError("solver failure: prior covariance is singular") from error
    normal = 0.5 * (prior_information + prior_information.T) + H
    normal = 0.5 * (normal + normal.T)
    try:
        factor = np.linalg.cholesky(normal)
        delta = -np.linalg.solve(factor.T, np.linalg.solve(factor, b))
        posterior = np.linalg.solve(factor.T, np.linalg.solve(factor, np.eye(6)))
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(normal)
        if not np.all(np.isfinite(eigenvalues)) or float(np.min(eigenvalues)) <= 1.0e-12:
            raise RuntimeError("solver failure: MAP normal matrix is not positive definite")
        inverse_values = 1.0 / eigenvalues
        posterior = (eigenvectors * inverse_values) @ eigenvectors.T
        delta = -(eigenvectors * inverse_values) @ (eigenvectors.T @ b)
    posterior = 0.5 * (posterior + posterior.T)
    if not np.all(np.isfinite(delta)) or not np.all(np.isfinite(posterior)):
        raise RuntimeError("solver failure: non-finite MAP output")
    if float(np.min(np.linalg.eigvalsh(posterior))) < -1.0e-10:
        raise RuntimeError("solver failure: posterior covariance is not PSD")
    return delta, posterior


def selective_attenuation_operator(direction: np.ndarray, alpha: float) -> np.ndarray:
    value = np.asarray(direction, dtype=float)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise ValueError("selective direction must be a finite length-3 vector")
    norm = float(np.linalg.norm(value))
    if norm <= 1.0e-12:
        raise ValueError("selective direction cannot be zero")
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("attenuation alpha must be in [0, 1]")
    unit = value / norm
    projector = np.outer(unit, unit)
    translation = np.eye(3) - (1.0 - np.sqrt(float(alpha))) * projector
    operator = np.eye(6)
    operator[3:6, 3:6] = translation
    return operator


def attenuate_normal_equation(
    normal: NormalEquation,
    strategy: str,
    alpha: float,
    degeneracy_triggered: bool,
    actionable_direction: bool,
    direction: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray]:
    H = normal.H
    b = normal.b
    if strategy == "huber_full":
        return H.copy(), b.copy()
    if strategy == "huber_global":
        if not degeneracy_triggered:
            return H.copy(), b.copy()
        return float(alpha) * H, float(alpha) * b
    if strategy in {"huber_selective", "huber_oracle_selective"}:
        if not actionable_direction:
            return H.copy(), b.copy()
        if direction is None:
            raise ValueError("actionable selective update requires a direction")
        if float(alpha) == 1.0:
            return H.copy(), b.copy()
        operator = selective_attenuation_operator(direction, alpha)
        effective_H = operator.T @ H @ operator
        effective_H = _project_psd_roundoff(effective_H, "selective information")
        return effective_H, operator.T @ b
    raise ValueError(f"unsupported update strategy: {strategy}")


def execute_update_strategy(
    strategy: str,
    prior_covariance: np.ndarray,
    normal: NormalEquation,
    alpha: float,
    degeneracy_triggered: bool,
    actionable_direction: bool,
    direction: Optional[np.ndarray] = None,
) -> UpdateResult:
    if strategy == "motion_only":
        covariance = _validated_psd(prior_covariance, "prior covariance", positive_definite=True)
        return UpdateResult(
            delta=np.zeros(6),
            posterior_covariance=covariance.copy(),
            effective_H=np.zeros((6, 6)),
            effective_b=np.zeros(6),
            strategy=strategy,
            degeneracy_triggered=bool(degeneracy_triggered),
            actionable_direction=False,
            attenuation_alpha=1.0,
            solver_condition_number=float(np.linalg.cond(np.linalg.solve(covariance, np.eye(6)))),
        )
    effective_H, effective_b = attenuate_normal_equation(
        normal,
        strategy,
        alpha,
        degeneracy_triggered,
        actionable_direction,
        direction,
    )
    delta, posterior = solve_map_update(prior_covariance, effective_H, effective_b)
    prior_information = np.linalg.solve(prior_covariance, np.eye(6))
    solver_condition = float(np.linalg.cond(prior_information + effective_H))
    return UpdateResult(
        delta=delta,
        posterior_covariance=posterior,
        effective_H=effective_H,
        effective_b=effective_b,
        strategy=strategy,
        degeneracy_triggered=bool(degeneracy_triggered),
        actionable_direction=bool(actionable_direction),
        attenuation_alpha=float(alpha),
        solver_condition_number=solver_condition,
    )


def _validated_psd(matrix: np.ndarray, name: str, positive_definite: bool) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.shape != (6, 6) or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be a finite 6x6 matrix")
    value = 0.5 * (value + value.T)
    eigenvalues, eigenvectors = np.linalg.eigh(value)
    tolerance = max(1.0e-10, 1.0e-12 * float(np.max(np.abs(eigenvalues))))
    if float(np.min(eigenvalues)) < -tolerance:
        raise ValueError(f"{name} is not PSD")
    floor = 1.0e-12 if positive_definite else 0.0
    clipped = np.maximum(eigenvalues, floor)
    return 0.5 * ((eigenvectors * clipped) @ eigenvectors.T + (eigenvectors * clipped) @ eigenvectors.T)


def _project_psd_roundoff(matrix: np.ndarray, name: str) -> np.ndarray:
    """Remove only scale-relative negative eigenvalues caused by roundoff."""

    value = np.asarray(matrix, dtype=float)
    value = 0.5 * (value + value.T)
    eigenvalues = np.linalg.eigvalsh(value)
    if float(np.min(eigenvalues)) >= 0.0:
        return value
    tolerance = max(1.0e-10, 1.0e-12 * float(np.max(np.abs(eigenvalues))))
    if float(np.min(eigenvalues)) < -tolerance:
        raise ValueError(f"{name} is not PSD")
    eigenvalues, eigenvectors = np.linalg.eigh(value)
    projected = (eigenvectors * np.maximum(eigenvalues, 0.0)) @ eigenvectors.T
    return 0.5 * (projected + projected.T)
