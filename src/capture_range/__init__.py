"""Algorithm-conditioned empirical directional capture-range primitives.

The package is deliberately independent of the FAST-LIO2 estimator.  It
contains only immutable measurement records, the repository-native pose
perturbation convention, recovery metrics, curve fitting, and deterministic
randomness helpers.
"""

from .capture_radius import (
    build_direction_recovery_curve,
    capture_radius_from_fitted,
    fit_nonincreasing_isotonic,
    wilson_interval,
    wilson_intervals,
)
from .perturbation import (
    apply_perturbation,
    apply_rotation_perturbation,
    apply_translation_perturbation,
)
from .randomness import (
    array_checksum,
    derive_trial_seed,
    mapping_checksum,
    noise_checksum,
    perturbation_checksum,
)
from .recovery_metrics import (
    DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD,
    DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
    evaluate_recovery_success,
    is_recovery_success,
    rotation_geodesic_error_rad,
    translation_error_m,
)
from .types import (
    DirectionRecoveryCurve,
    PerturbationSpec,
    RecoveryTrialResult,
    RegistrationSnapshot,
)

__all__ = [
    "DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD",
    "DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M",
    "DirectionRecoveryCurve",
    "PerturbationSpec",
    "RecoveryTrialResult",
    "RegistrationSnapshot",
    "apply_perturbation",
    "apply_rotation_perturbation",
    "apply_translation_perturbation",
    "array_checksum",
    "build_direction_recovery_curve",
    "capture_radius_from_fitted",
    "derive_trial_seed",
    "evaluate_recovery_success",
    "fit_nonincreasing_isotonic",
    "is_recovery_success",
    "mapping_checksum",
    "noise_checksum",
    "perturbation_checksum",
    "rotation_geodesic_error_rad",
    "translation_error_m",
    "wilson_interval",
    "wilson_intervals",
]
