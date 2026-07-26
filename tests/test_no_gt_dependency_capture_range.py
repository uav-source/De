import inspect
from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

from capture_range.full_reassociation_runner import run_full_reassociation_trial
from capture_range.registration_core import run_full_reassociation_core
from capture_range.snapshot import build_smoke_snapshots
from capture_range.types import PerturbationSpec


ROOT = Path(__file__).resolve().parents[1]


def _rich_snapshot():
    protocol = yaml.safe_load(
        (ROOT / "configs/capture_range/day1_protocol.yaml").read_text(
            encoding="utf-8"
        )
    )
    return build_smoke_snapshots(protocol)[0]


def test_optimizer_core_has_only_registration_inputs():
    assert list(inspect.signature(run_full_reassociation_core).parameters) == [
        "scan_points",
        "local_map_points",
        "initial_pose",
        "registration_config",
        "seed",
    ]


def test_poisoning_or_removing_evaluation_metadata_cannot_change_registration():
    snapshot = _rich_snapshot()
    poisoned = replace(
        snapshot,
        metadata={
            "ground_truth_weak_direction": [999.0, -999.0, 17.0],
            "pose_gt": "must_not_be_read",
            "axis_gt": {"poison": True},
        },
    )
    stripped = replace(snapshot, metadata={})
    perturbation = PerturbationSpec(
        perturbation_type="translation",
        direction=np.array([0.0, 1.0, 0.0]),
        signed_amplitude=-0.10,
        repeat_index=1,
        seed=17003,
        direction_id="-y",
        signed_side=-1,
    )

    first = run_full_reassociation_trial(poisoned, perturbation)
    second = run_full_reassociation_trial(stripped, perturbation)

    np.testing.assert_array_equal(first.initial_pose, second.initial_pose)
    np.testing.assert_array_equal(first.final_pose, second.final_pose)
    assert first.iteration_count == second.iteration_count
    assert first.initial_cost == second.initial_cost
    assert first.final_cost == second.final_cost
    assert first.correspondence_checksum == second.correspondence_checksum
    assert first.success == second.success


def test_registration_sources_do_not_name_forbidden_evaluation_inputs():
    forbidden = [
        "ground" + "_truth_weak_direction",
        "pose" + "_gt",
        "axis" + "_gt",
    ]
    paths = [
        ROOT / "src/capture_range/registration_core.py",
        ROOT / "src/capture_range/full_reassociation_runner.py",
        ROOT / "src/capture_range/frozen_jacobian_runner.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source
