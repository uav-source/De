from dataclasses import fields, replace

import numpy as np
import pytest

from capture_range import registration_core
from capture_range.full_reassociation_runner import (
    prepare_full_reassociation_trial_session,
    run_full_reassociation_trial,
    run_prepared_full_reassociation_trial,
)
from capture_range.registration_core import (
    prepare_full_reassociation_session,
    run_full_reassociation_core,
    run_prepared_full_reassociation_core,
)
from capture_range.types import PerturbationSpec, RegistrationSnapshot


def _sentinel_snapshot() -> RegistrationSnapshot:
    coordinates = np.linspace(-0.8, 0.8, 5)
    local_map = []
    for first in coordinates:
        for second in coordinates:
            local_map.extend(
                (
                    [first, second, 0.0],
                    [first, 0.0, second],
                    [0.0, first, second],
                )
            )
    local_map_points = np.unique(np.asarray(local_map, dtype=np.float64), axis=0)
    scan_points = local_map_points[::2]
    return RegistrationSnapshot(
        snapshot_id="sentinel_prepared_session",
        scan_points=scan_points,
        local_map_points=local_map_points,
        reference_pose=np.eye(4),
        registration_config={
            "registration": {
                "k_neighbors": 5,
                "max_neighbor_distance_m": 0.8,
                "plane_fit_tolerance_m": 0.05,
                "huber_delta_m": 0.05,
                "damping": 1.0e-6,
                "rotation_step_tolerance_rad": 1.0e-7,
                "translation_step_tolerance_m": 1.0e-7,
                "min_correspondences": 6,
                "max_iterations": 8,
            }
        },
        metadata={"fixture": "non_day2_sentinel"},
    )


def _perturbation() -> PerturbationSpec:
    return PerturbationSpec(
        perturbation_type="translation",
        direction=np.array([1.0, 0.0, 0.0]),
        signed_amplitude=0.03,
        repeat_index=0,
        seed=4242,
        direction_id="sentinel_positive_x",
        signed_side=1,
    )


def _assert_outcomes_equal(first, second) -> None:
    for field in fields(first):
        first_value = getattr(first, field.name)
        second_value = getattr(second, field.name)
        if isinstance(first_value, np.ndarray):
            np.testing.assert_array_equal(first_value, second_value)
        elif field.name in {"initial_evaluation", "final_evaluation"}:
            for evaluation_field in fields(first_value):
                left = getattr(first_value, evaluation_field.name)
                right = getattr(second_value, evaluation_field.name)
                if isinstance(left, np.ndarray):
                    np.testing.assert_array_equal(left, right)
                else:
                    assert left == right
        else:
            assert first_value == second_value


def test_prepared_core_is_numerically_and_instrumentally_identical():
    snapshot = _sentinel_snapshot()
    perturbation = _perturbation()
    initial_pose = snapshot.reference_pose.copy()
    initial_pose[0, 3] = perturbation.signed_amplitude

    original = run_full_reassociation_core(
        snapshot.scan_points,
        snapshot.local_map_points,
        initial_pose,
        snapshot.registration_config,
        perturbation.seed,
    )
    prepared = prepare_full_reassociation_session(
        snapshot.scan_points,
        snapshot.local_map_points,
        snapshot.registration_config,
        snapshot_id=snapshot.snapshot_id,
        reference_pose=snapshot.reference_pose,
    )
    reused = run_prepared_full_reassociation_core(
        prepared, initial_pose, perturbation.seed
    )

    _assert_outcomes_equal(original, reused)
    assert prepared.scan_points.flags.writeable is False
    assert prepared.local_map_points.flags.writeable is False


def test_prepared_runner_matches_original_except_wall_clock_runtime():
    snapshot = _sentinel_snapshot()
    perturbation = _perturbation()
    original = run_full_reassociation_trial(snapshot, perturbation)
    prepared = prepare_full_reassociation_trial_session(snapshot)
    reused = run_prepared_full_reassociation_trial(
        snapshot, perturbation, prepared
    )

    for field in fields(original):
        if field.name == "runtime_ms":
            continue
        left = getattr(original, field.name)
        right = getattr(reused, field.name)
        if isinstance(left, np.ndarray):
            np.testing.assert_array_equal(left, right)
        else:
            assert left == right


def test_prepared_session_builds_one_tree_but_reassociates_every_evaluation(
    monkeypatch,
):
    snapshot = _sentinel_snapshot()
    perturbation = _perturbation()
    tree_build_count = 0
    query_count = 0
    original_tree = registration_core.cKDTree
    original_query = registration_core._query_neighbors

    def counted_tree(*args, **kwargs):
        nonlocal tree_build_count
        tree_build_count += 1
        return original_tree(*args, **kwargs)

    def counted_query(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        return original_query(*args, **kwargs)

    monkeypatch.setattr(registration_core, "cKDTree", counted_tree)
    monkeypatch.setattr(registration_core, "_query_neighbors", counted_query)
    prepared = prepare_full_reassociation_trial_session(snapshot)
    first = run_prepared_full_reassociation_trial(snapshot, perturbation, prepared)
    second = run_prepared_full_reassociation_trial(snapshot, perturbation, prepared)

    assert tree_build_count == 1
    assert query_count == (
        first.full_reassociation_count + second.full_reassociation_count
    )
    assert first.correspondence_checksum_trace == second.correspondence_checksum_trace


@pytest.mark.parametrize(
    "mismatched",
    [
        lambda snapshot: replace(snapshot, snapshot_id="different_snapshot"),
        lambda snapshot: replace(
            snapshot,
            scan_points=np.asarray(snapshot.scan_points)
            + np.array([1.0e-3, 0.0, 0.0]),
        ),
        lambda snapshot: replace(
            snapshot,
            local_map_points=np.asarray(snapshot.local_map_points)
            + np.array([0.0, 1.0e-3, 0.0]),
        ),
        lambda snapshot: replace(
            snapshot,
            reference_pose=np.asarray(snapshot.reference_pose)
            @ np.array(
                [
                    [1.0, 0.0, 0.0, 1.0e-3],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            ),
        ),
        lambda snapshot: replace(
            snapshot,
            registration_config={
                "registration": {
                    **dict(snapshot.registration_config["registration"]),
                    "damping": 2.0e-6,
                }
            },
        ),
    ],
)
def test_prepared_runner_rejects_snapshot_mismatch(mismatched):
    snapshot = _sentinel_snapshot()
    prepared = prepare_full_reassociation_trial_session(snapshot)

    with pytest.raises(ValueError, match="snapshot mismatch"):
        run_prepared_full_reassociation_trial(
            mismatched(snapshot), _perturbation(), prepared
        )
