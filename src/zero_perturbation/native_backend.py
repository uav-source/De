"""Audited native full-reassociation and frozen-Jacobian adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from capture_range.registration_core import (
    RegistrationOutcome,
    prepare_frozen_linearization,
    prepare_full_reassociation_session,
    run_frozen_jacobian_core,
    run_prepared_full_reassociation_core,
)

from .correspondence_turnover import correspondence_turnover, normal_angle_turnover
from .metrics import full_frozen_pose_difference, traditional_information_metrics
from .types import BackendResult


@dataclass(frozen=True)
class NativePairResult:
    full: BackendResult
    frozen: BackendResult
    turnover: Mapping[str, Any]
    normal_turnover: Mapping[str, Any]
    full_frozen: Mapping[str, float]
    traditional_metrics: Mapping[str, float]


def _backend_result(
    backend: str,
    outcome: RegistrationOutcome,
    runtime_ms: float,
    input_checksum: str,
) -> BackendResult:
    return BackendResult(
        backend=backend,
        final_pose=outcome.final_pose,
        runtime_ms=runtime_ms,
        solver_converged=bool(outcome.solver_converged),
        finite_result=bool(outcome.finite_result),
        iteration_count=int(outcome.iteration_count),
        correspondence_count=int(outcome.final_evaluation.correspondence_count),
        initial_cost=float(outcome.initial_evaluation.cost),
        final_cost=float(outcome.final_evaluation.cost),
        termination_reason=str(outcome.termination_reason),
        failure_reason=str(outcome.failure_reason),
        extra={
            "backend_input_checksum": str(input_checksum),
            "initial_correspondence_checksum": outcome.initial_evaluation.correspondence_checksum,
            "final_correspondence_checksum": outcome.final_evaluation.correspondence_checksum,
            "full_reassociation_count": int(outcome.counters.full_reassociation_count),
            "plane_fit_count": int(outcome.counters.plane_fit_count),
            "jacobian_recompute_count": int(outcome.counters.jacobian_recompute_count),
        },
    )


def run_native_pair(
    scan_points: np.ndarray,
    map_points: np.ndarray,
    initial_pose: np.ndarray,
    registration_config: Mapping[str, Any],
    backend_seed: int,
    input_checksum: str,
) -> NativePairResult:
    """Run both native paths without accepting scene labels or GT directions."""

    prepared = prepare_full_reassociation_session(
        scan_points,
        map_points,
        registration_config,
        snapshot_id=str(input_checksum),
        reference_pose=initial_pose,
    )
    start = time.perf_counter()
    full_outcome = run_prepared_full_reassociation_core(
        prepared, initial_pose, int(backend_seed)
    )
    full_runtime_ms = (time.perf_counter() - start) * 1000.0

    baseline = prepare_frozen_linearization(
        scan_points,
        map_points,
        initial_pose,
        registration_config,
        int(backend_seed),
        snapshot_id=str(input_checksum),
    )
    start = time.perf_counter()
    frozen_outcome = run_frozen_jacobian_core(
        baseline, initial_pose, registration_config, int(backend_seed)
    )
    frozen_runtime_ms = (time.perf_counter() - start) * 1000.0

    traditional = traditional_information_metrics(
        full_outcome.initial_evaluation, registration_config
    )
    traditional["initial_cost"] = float(full_outcome.initial_evaluation.cost)
    traditional["final_cost"] = float(full_outcome.final_evaluation.cost)
    return NativePairResult(
        full=_backend_result(
            "native_full", full_outcome, full_runtime_ms, input_checksum
        ),
        frozen=_backend_result(
            "native_frozen", frozen_outcome, frozen_runtime_ms, input_checksum
        ),
        turnover=correspondence_turnover(
            full_outcome.initial_evaluation, full_outcome.final_evaluation
        ),
        normal_turnover=normal_angle_turnover(
            full_outcome.initial_evaluation, full_outcome.final_evaluation
        ),
        full_frozen=full_frozen_pose_difference(
            full_outcome.final_pose, frozen_outcome.final_pose
        ),
        traditional_metrics=traditional,
    )


__all__ = ["NativePairResult", "run_native_pair"]
