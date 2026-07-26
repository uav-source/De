"""Isolated frozen-Jacobian comparison runner."""

from __future__ import annotations

import time

import numpy as np

from .full_reassociation_runner import _result_from_outcome
from .perturbation import apply_perturbation
from .registration_core import (
    FrozenJacobianBaseline,
    array_checksum,
    config_checksum,
    prepare_frozen_linearization,
    run_frozen_jacobian_core,
)
from .types import PerturbationSpec, RecoveryTrialResult, RegistrationSnapshot


def prepare_frozen_jacobian_baseline(
    snapshot: RegistrationSnapshot,
    *,
    seed: int = 0,
) -> FrozenJacobianBaseline:
    """Prepare one reusable reference model outside all comparison trials."""

    return prepare_frozen_linearization(
        snapshot.scan_points,
        snapshot.local_map_points,
        snapshot.reference_pose,
        snapshot.registration_config,
        seed,
        snapshot_id=snapshot.snapshot_id,
    )


def run_frozen_jacobian_trial(
    snapshot: RegistrationSnapshot,
    perturbation: PerturbationSpec,
    *,
    baseline: FrozenJacobianBaseline,
) -> RecoveryTrialResult:
    """Run one baseline-only trial without trial-time geometric rebuilding.

    Baseline preparation is deliberately a separate, explicit operation.  A
    trial therefore cannot hide reference-pose association or Jacobian work
    behind zero-valued trial counters.
    """
    _validate_baseline(snapshot, baseline)

    started = time.perf_counter()
    initial_pose = apply_perturbation(snapshot.reference_pose, perturbation)
    outcome = run_frozen_jacobian_core(
        baseline,
        initial_pose,
        snapshot.registration_config,
        perturbation.seed,
    )
    runtime_ms = (time.perf_counter() - started) * 1000.0
    counters = outcome.counters
    forbidden_counts = (
        counters.full_reassociation_count,
        counters.transform_count,
        counters.nearest_neighbor_search_count,
        counters.correspondence_build_count,
        counters.plane_fit_count,
        counters.jacobian_recompute_count,
    )
    if any(forbidden_counts):
        raise RuntimeError("frozen-Jacobian comparison leaked formal registration work")
    return _result_from_outcome(
        snapshot,
        perturbation,
        initial_pose,
        outcome,
        runtime_ms,
        full_reassociation=False,
        baseline_only=True,
    )


def _validate_baseline(
    snapshot: RegistrationSnapshot, baseline: FrozenJacobianBaseline
) -> None:
    if baseline.snapshot_id and baseline.snapshot_id != snapshot.snapshot_id:
        raise ValueError("frozen baseline snapshot_id mismatch")
    if baseline.scan_checksum != array_checksum(snapshot.scan_points):
        raise ValueError("frozen baseline scan mismatch")
    if baseline.map_checksum != array_checksum(snapshot.local_map_points):
        raise ValueError("frozen baseline map mismatch")
    if baseline.config_checksum != config_checksum(snapshot.registration_config):
        raise ValueError("frozen baseline registration configuration mismatch")
    if not np.array_equal(baseline.reference_pose, snapshot.reference_pose):
        raise ValueError("frozen baseline reference pose mismatch")


# Compatibility aliases.
build_frozen_jacobian_baseline = prepare_frozen_jacobian_baseline
run_frozen_jacobian = run_frozen_jacobian_trial
