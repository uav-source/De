"""Robust whitened gain-update primitives for Stage 2C."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class RobustLinearSystem:
    whitened_jacobian: np.ndarray
    whitened_residual: np.ndarray
    H: np.ndarray
    b: np.ndarray
    robust_weights: np.ndarray
    sqrt_precision: np.ndarray


@dataclass(frozen=True)
class GainUpdate:
    delta: np.ndarray
    posterior_covariance: np.ndarray
    kalman_gain_whitened: np.ndarray
    normal_condition_number: float
    joseph_min_eigenvalue: float


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


def build_robust_linear_system(
    J: np.ndarray,
    residual: np.ndarray,
    variance: np.ndarray,
    huber_delta_sigma: float,
) -> RobustLinearSystem:
    jacobian = np.asarray(J, dtype=float)
    values = np.asarray(residual, dtype=float)
    variances = np.asarray(variance, dtype=float)
    if jacobian.ndim != 2 or jacobian.shape[1] != 6 or jacobian.shape[0] != values.size:
        raise ValueError("J must have shape [N, 6] and match residual")
    if values.shape != variances.shape or not np.all(np.isfinite(jacobian)):
        raise ValueError("robust linear-system inputs have inconsistent shapes or non-finite values")
    robust = huber_weights(values, variances, huber_delta_sigma)
    sqrt_precision = np.sqrt(robust / variances)
    whitened_jacobian = jacobian * sqrt_precision[:, None]
    whitened_residual = values * sqrt_precision
    H = _project_psd_roundoff(whitened_jacobian.T @ whitened_jacobian, "Huber information")
    b = whitened_jacobian.T @ whitened_residual
    return RobustLinearSystem(
        whitened_jacobian=whitened_jacobian,
        whitened_residual=whitened_residual,
        H=H,
        b=b,
        robust_weights=robust,
        sqrt_precision=sqrt_precision,
    )


def build_normal_equation(
    J: np.ndarray,
    residual: np.ndarray,
    variance: np.ndarray,
    huber_delta_sigma: float,
) -> RobustLinearSystem:
    """Deprecated compatibility wrapper; active code uses the whitened system."""

    warnings.warn(
        "build_normal_equation is deprecated; use build_robust_linear_system",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_robust_linear_system(J, residual, variance, huber_delta_sigma)


def solve_map_update(
    prior_covariance: np.ndarray,
    effective_H: np.ndarray,
    effective_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compatibility information-form solver retained for historical tests."""

    covariance = _validated_covariance(prior_covariance, "prior covariance", positive_definite=True)
    H = _validated_information(effective_H, "effective information")
    b = np.asarray(effective_b, dtype=float)
    if b.shape != (6,) or not np.all(np.isfinite(b)):
        raise ValueError("effective_b must be a finite length-6 vector")
    prior_information = _solve_spd(covariance, np.eye(6), "prior covariance")
    normal = 0.5 * (prior_information + prior_information.T) + H
    posterior = _solve_spd(normal, np.eye(6), "MAP normal matrix")
    delta = -posterior @ b
    return delta, _validate_posterior(posterior)


def solve_full_robust_gain(
    prior_covariance: np.ndarray,
    system: RobustLinearSystem,
) -> GainUpdate:
    covariance = _validated_covariance(prior_covariance, "prior covariance", positive_definite=True)
    A = np.asarray(system.whitened_jacobian, dtype=float)
    y = np.asarray(system.whitened_residual, dtype=float)
    if A.ndim != 2 or A.shape[1] != 6 or y.shape != (A.shape[0],):
        raise ValueError("whitened system has inconsistent shapes")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(y)):
        raise ValueError("whitened system must be finite")
    prior_information = _solve_spd(covariance, np.eye(6), "prior covariance")
    normal = 0.5 * (prior_information + prior_information.T) + system.H
    posterior_information = _solve_spd(normal, np.eye(6), "robust normal matrix")
    gain = posterior_information @ A.T
    delta = -gain @ y
    joseph = _joseph_covariance(covariance, A, gain)
    if not np.allclose(posterior_information, joseph, atol=1.0e-10, rtol=1.0e-7):
        difference = float(np.max(np.abs(posterior_information - joseph)))
        raise RuntimeError(f"information/Joseph covariance mismatch: {difference}")
    return _gain_update(delta, joseph, gain, normal)


def make_translation_direction_6d(direction: np.ndarray) -> np.ndarray:
    value = np.asarray(direction, dtype=float)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise ValueError("direction must be a finite length-3 vector")
    norm = float(np.linalg.norm(value))
    if norm <= 1.0e-12:
        raise ValueError("direction cannot be zero")
    lifted = np.zeros(6, dtype=float)
    lifted[3:6] = value / norm
    return lifted


def directional_correction_projector(direction: np.ndarray, alpha: float) -> np.ndarray:
    _validate_alpha(alpha)
    lifted = make_translation_direction_6d(direction)
    return np.eye(6) - (1.0 - float(alpha)) * np.outer(lifted, lifted)


def apply_projected_gain_update(
    prior_covariance: np.ndarray,
    system: RobustLinearSystem,
    direction: np.ndarray,
    alpha: float,
) -> GainUpdate:
    full = solve_full_robust_gain(prior_covariance, system)
    if float(alpha) == 1.0:
        return full
    projector = directional_correction_projector(direction, alpha)
    gain = projector @ full.kalman_gain_whitened
    delta = -gain @ system.whitened_residual
    posterior = _joseph_covariance(prior_covariance, system.whitened_jacobian, gain)
    update = _gain_update(delta, posterior, gain, _normal_matrix(prior_covariance, system.H))
    _validate_projected_correction(full.delta, update.delta, direction, alpha)
    return update


def apply_global_gain_update(
    prior_covariance: np.ndarray,
    system: RobustLinearSystem,
    alpha: float,
) -> GainUpdate:
    _validate_alpha(alpha)
    full = solve_full_robust_gain(prior_covariance, system)
    if float(alpha) == 1.0:
        return full
    gain = float(alpha) * full.kalman_gain_whitened
    delta = -gain @ system.whitened_residual
    posterior = _joseph_covariance(prior_covariance, system.whitened_jacobian, gain)
    update = _gain_update(delta, posterior, gain, _normal_matrix(prior_covariance, system.H))
    if not np.allclose(update.delta, float(alpha) * full.delta, atol=1.0e-10, rtol=0.0):
        raise RuntimeError("global gain did not scale the full correction exactly")
    return update


def apply_directional_mode_update(
    prior_covariance: np.ndarray,
    system: RobustLinearSystem,
    direction: np.ndarray,
    alpha: float,
) -> GainUpdate:
    _validate_alpha(alpha)
    lifted = make_translation_direction_6d(direction)
    A = system.whitened_jacobian
    y = system.whitened_residual
    response = A @ lifted
    squared_norm = float(response @ response)
    if squared_norm < 1.0e-12 or float(alpha) == 1.0:
        return solve_full_robust_gain(prior_covariance, system)
    mode = response / np.sqrt(squared_norm)
    coefficient = 1.0 - np.sqrt(float(alpha))
    A_mode = A - coefficient * np.outer(mode, mode @ A)
    y_mode = y - coefficient * mode * float(mode @ y)
    mode_system = RobustLinearSystem(
        whitened_jacobian=A_mode,
        whitened_residual=y_mode,
        H=_project_psd_roundoff(A_mode.T @ A_mode, "directional-mode information"),
        b=A_mode.T @ y_mode,
        robust_weights=system.robust_weights.copy(),
        sqrt_precision=system.sqrt_precision.copy(),
    )
    realized = float(lifted @ mode_system.H @ lifted)
    expected = float(alpha) * float(lifted @ system.H @ lifted)
    if not np.isclose(realized, expected, atol=1.0e-10, rtol=1.0e-9):
        raise RuntimeError("directional measurement mode did not realize the requested information ratio")
    return solve_full_robust_gain(prior_covariance, mode_system)


def execute_gain_strategy(
    strategy: str,
    prior_covariance: np.ndarray,
    system: RobustLinearSystem,
    alpha: float,
    degeneracy_triggered: bool,
    actionable_direction: bool,
    direction: Optional[np.ndarray] = None,
) -> GainUpdate:
    full = solve_full_robust_gain(prior_covariance, system)
    if strategy == "huber_full":
        return full
    if strategy == "huber_global_gain":
        return apply_global_gain_update(prior_covariance, system, alpha) if degeneracy_triggered else full
    if strategy == "huber_directional_mode":
        if not actionable_direction:
            return full
        if direction is None:
            raise ValueError("directional mode requires an actionable direction")
        return apply_directional_mode_update(prior_covariance, system, direction, alpha)
    if strategy in {"huber_projected_gain", "huber_oracle_projected_gain"}:
        if not actionable_direction:
            return full
        if direction is None:
            raise ValueError("projected gain requires an actionable direction")
        return apply_projected_gain_update(prior_covariance, system, direction, alpha)
    raise ValueError(f"unsupported gain strategy: {strategy}")


def _validate_projected_correction(
    full: np.ndarray,
    projected: np.ndarray,
    direction: np.ndarray,
    alpha: float,
) -> None:
    lifted = make_translation_direction_6d(direction)
    weak_full = float(lifted @ full)
    weak_projected = float(lifted @ projected)
    if not np.isclose(weak_projected, float(alpha) * weak_full, atol=1.0e-10, rtol=0.0):
        raise RuntimeError("projected gain weak correction ratio mismatch")
    strong_projector = np.eye(6) - np.outer(lifted, lifted)
    if not np.allclose(strong_projector @ projected, strong_projector @ full, atol=1.0e-10, rtol=0.0):
        raise RuntimeError("projected gain changed an orthogonal correction component")


def _joseph_covariance(covariance: np.ndarray, A: np.ndarray, gain: np.ndarray) -> np.ndarray:
    prior = _validated_covariance(covariance, "prior covariance", positive_definite=True)
    identity_minus_gain = np.eye(6) - gain @ A
    posterior = identity_minus_gain @ prior @ identity_minus_gain.T + gain @ gain.T
    return _validate_posterior(posterior)


def _gain_update(delta: np.ndarray, posterior: np.ndarray, gain: np.ndarray, normal: np.ndarray) -> GainUpdate:
    values = [np.asarray(delta), np.asarray(posterior), np.asarray(gain)]
    if not all(np.all(np.isfinite(value)) for value in values):
        raise RuntimeError("solver failure: non-finite gain output")
    posterior = _validate_posterior(posterior)
    return GainUpdate(
        delta=np.asarray(delta, dtype=float),
        posterior_covariance=posterior,
        kalman_gain_whitened=np.asarray(gain, dtype=float),
        normal_condition_number=float(np.linalg.cond(normal)),
        joseph_min_eigenvalue=float(np.min(np.linalg.eigvalsh(posterior))),
    )


def _normal_matrix(prior_covariance: np.ndarray, H: np.ndarray) -> np.ndarray:
    covariance = _validated_covariance(prior_covariance, "prior covariance", positive_definite=True)
    prior_information = _solve_spd(covariance, np.eye(6), "prior covariance")
    return 0.5 * (prior_information + prior_information.T) + H


def _solve_spd(matrix: np.ndarray, right: np.ndarray, name: str) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    try:
        factor = np.linalg.cholesky(value)
        return np.linalg.solve(factor.T, np.linalg.solve(factor, right))
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (value + value.T))
        if not np.all(np.isfinite(eigenvalues)) or float(np.min(eigenvalues)) <= 1.0e-12:
            raise RuntimeError(f"solver failure: {name} is not positive definite")
        transformed = eigenvectors.T @ right
        return eigenvectors @ (transformed / eigenvalues[:, None] if transformed.ndim == 2 else transformed / eigenvalues)


def _validated_covariance(matrix: np.ndarray, name: str, positive_definite: bool) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.shape != (6, 6) or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be a finite 6x6 matrix")
    value = 0.5 * (value + value.T)
    eigenvalues, eigenvectors = np.linalg.eigh(value)
    if float(np.min(eigenvalues)) < -1.0e-10:
        raise ValueError(f"{name} is not PSD")
    floor = 1.0e-12 if positive_definite else 0.0
    clipped = np.maximum(eigenvalues, floor)
    projected = (eigenvectors * clipped) @ eigenvectors.T
    return 0.5 * (projected + projected.T)


def _validated_information(matrix: np.ndarray, name: str) -> np.ndarray:
    return _project_psd_roundoff(matrix, name)


def _validate_posterior(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.shape != (6, 6) or not np.all(np.isfinite(value)):
        raise RuntimeError("solver failure: posterior covariance must be finite and 6x6")
    value = 0.5 * (value + value.T)
    eigenvalues, eigenvectors = np.linalg.eigh(value)
    if float(np.min(eigenvalues)) < -1.0e-10:
        raise RuntimeError("solver failure: Joseph posterior covariance is not PSD")
    projected = (eigenvectors * np.maximum(eigenvalues, 0.0)) @ eigenvectors.T
    return 0.5 * (projected + projected.T)


def _project_psd_roundoff(matrix: np.ndarray, name: str) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.shape != (6, 6) or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be a finite 6x6 matrix")
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


def _validate_alpha(alpha: float) -> None:
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("attenuation alpha must be in [0, 1]")
