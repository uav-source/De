"""Formal full-reassociation recovery-trial runner."""

from __future__ import annotations

import math
import time
from typing import Any, Mapping

from .perturbation import apply_perturbation
from .recovery_metrics import (
    DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD,
    DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
    evaluate_recovery_success,
    rotation_geodesic_error_rad,
    translation_error_m,
)
from .registration_core import (
    PreparedFullReassociationSession,
    RegistrationOutcome,
    assert_prepared_full_reassociation_matches,
    prepare_full_reassociation_session,
    run_full_reassociation_core,
    run_prepared_full_reassociation_core,
)
from .types import PerturbationSpec, RecoveryTrialResult, RegistrationSnapshot


def run_full_reassociation_trial(
    snapshot: RegistrationSnapshot,
    perturbation: PerturbationSpec,
) -> RecoveryTrialResult:
    """Run one formal trial and evaluate recovery only after optimization."""

    started = time.perf_counter()
    initial_pose = apply_perturbation(snapshot.reference_pose, perturbation)
    outcome = run_full_reassociation_core(
        snapshot.scan_points,
        snapshot.local_map_points,
        initial_pose,
        snapshot.registration_config,
        perturbation.seed,
    )
    runtime_ms = (time.perf_counter() - started) * 1000.0
    if outcome.counters.full_reassociation_count < 1:
        raise RuntimeError("formal recovery trial did not execute full reassociation")
    return _result_from_outcome(
        snapshot,
        perturbation,
        initial_pose,
        outcome,
        runtime_ms,
        full_reassociation=True,
        baseline_only=False,
    )


def prepare_full_reassociation_trial_session(
    snapshot: RegistrationSnapshot,
) -> PreparedFullReassociationSession:
    """Prepare the reusable spatial index for one immutable snapshot."""

    return prepare_full_reassociation_session(
        snapshot.scan_points,
        snapshot.local_map_points,
        snapshot.registration_config,
        snapshot_id=snapshot.snapshot_id,
        reference_pose=snapshot.reference_pose,
    )


def run_prepared_full_reassociation_trial(
    snapshot: RegistrationSnapshot,
    perturbation: PerturbationSpec,
    prepared: PreparedFullReassociationSession,
) -> RecoveryTrialResult:
    """Run one formal trial with a previously prepared matching snapshot."""

    assert_prepared_full_reassociation_matches(
        prepared,
        snapshot.scan_points,
        snapshot.local_map_points,
        snapshot.registration_config,
        snapshot_id=snapshot.snapshot_id,
        reference_pose=snapshot.reference_pose,
    )
    started = time.perf_counter()
    initial_pose = apply_perturbation(snapshot.reference_pose, perturbation)
    outcome = run_prepared_full_reassociation_core(
        prepared,
        initial_pose,
        perturbation.seed,
    )
    runtime_ms = (time.perf_counter() - started) * 1000.0
    if outcome.counters.full_reassociation_count < 1:
        raise RuntimeError("formal recovery trial did not execute full reassociation")
    return _result_from_outcome(
        snapshot,
        perturbation,
        initial_pose,
        outcome,
        runtime_ms,
        full_reassociation=True,
        baseline_only=False,
    )


def _result_from_outcome(
    snapshot: RegistrationSnapshot,
    perturbation: PerturbationSpec,
    initial_pose,
    outcome: RegistrationOutcome,
    runtime_ms: float,
    *,
    full_reassociation: bool,
    baseline_only: bool,
) -> RecoveryTrialResult:
    translation_error = translation_error_m(
        outcome.final_pose, snapshot.reference_pose
    )
    rotation_error = rotation_geodesic_error_rad(
        outcome.final_pose, snapshot.reference_pose
    )
    translation_threshold, rotation_threshold = _success_thresholds(
        snapshot.registration_config
    )
    finite_result = bool(
        outcome.finite_result
        and math.isfinite(translation_error)
        and math.isfinite(rotation_error)
        and math.isfinite(outcome.final_evaluation.cost)
    )
    success = evaluate_recovery_success(
        translation_error,
        rotation_error,
        solver_converged=outcome.solver_converged,
        finite_result=finite_result,
        iteration_limit_not_failed=outcome.iteration_limit_not_failed,
        translation_success_threshold_m=translation_threshold,
        rotation_success_threshold_rad=rotation_threshold,
    )
    failure_reason = outcome.failure_reason
    if not success and not failure_reason:
        if not finite_result:
            failure_reason = "nonfinite_result"
        elif not outcome.solver_converged:
            failure_reason = "solver_not_converged"
        else:
            failure_reason = "recovery_threshold_not_met"

    counters = outcome.counters
    initial = outcome.initial_evaluation
    final = outcome.final_evaluation
    return RecoveryTrialResult(
        snapshot_id=snapshot.snapshot_id,
        perturbation_type=perturbation.perturbation_type,
        direction_id=perturbation.direction_id,
        signed_amplitude=perturbation.signed_amplitude,
        repeat_index=perturbation.repeat_index,
        initial_pose=initial_pose,
        final_pose=outcome.final_pose,
        translation_error_m=translation_error,
        rotation_error_rad=rotation_error,
        final_cost=final.cost,
        correspondence_count=final.correspondence_count,
        iteration_count=outcome.iteration_count,
        solver_converged=outcome.solver_converged,
        finite_result=finite_result,
        success=success,
        runtime_ms=float(runtime_ms),
        full_reassociation=bool(full_reassociation),
        failure_reason=failure_reason,
        initial_correspondence_count=initial.correspondence_count,
        final_correspondence_count=final.correspondence_count,
        correspondence_checksum=final.correspondence_checksum,
        initial_correspondence_checksum=initial.correspondence_checksum,
        initial_cost=initial.cost,
        termination_reason=outcome.termination_reason,
        iteration_limit_not_failed=outcome.iteration_limit_not_failed,
        full_reassociation_count=counters.full_reassociation_count,
        baseline_only=bool(baseline_only),
        plane_fit_count=counters.plane_fit_count,
        transform_count=counters.transform_count,
        nearest_neighbor_search_count=counters.nearest_neighbor_search_count,
        correspondence_build_count=counters.correspondence_build_count,
        jacobian_recompute_count=counters.jacobian_recompute_count,
        jacobian_recomputation_count=counters.jacobian_recompute_count,
        signed_side=perturbation.signed_side,
        correspondence_checksum_trace=tuple(counters.correspondence_checksums),
    )


def _success_thresholds(config: Mapping[str, Any]) -> tuple[float, float]:
    success: Mapping[str, Any] = {}
    nested = config.get("success") if isinstance(config, Mapping) else None
    if isinstance(nested, Mapping):
        success = nested
    translation = float(
        success.get(
            "translation_error_threshold_m",
            success.get(
                "translation_success_threshold_m",
                DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
            ),
        )
    )
    if "rotation_geodesic_error_threshold_rad" in success:
        rotation = float(success["rotation_geodesic_error_threshold_rad"])
    elif "rotation_success_threshold_rad" in success:
        rotation = float(success["rotation_success_threshold_rad"])
    elif "rotation_geodesic_error_threshold_deg" in success:
        rotation = math.radians(
            float(success["rotation_geodesic_error_threshold_deg"])
        )
    elif "rotation_success_threshold_deg" in success:
        rotation = math.radians(float(success["rotation_success_threshold_deg"]))
    else:
        rotation = DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD
    return translation, rotation


# Compatibility alias for callers that use the path name as the verb.
run_full_reassociation = run_full_reassociation_trial
run_prepared_full_reassociation = run_prepared_full_reassociation_trial
