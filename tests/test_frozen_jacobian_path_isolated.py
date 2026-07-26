from pathlib import Path
import inspect

import numpy as np
import yaml

from capture_range import registration_core
from capture_range.frozen_jacobian_runner import (
    prepare_frozen_jacobian_baseline,
    run_frozen_jacobian_trial,
)
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


def test_frozen_trial_performs_no_trial_time_geometry_or_jacobian_work(monkeypatch):
    snapshot = _rich_snapshot()
    baseline = prepare_frozen_jacobian_baseline(snapshot, seed=17002)
    perturbation = PerturbationSpec(
        perturbation_type="rotation",
        direction=np.array([0.0, 0.0, 1.0]),
        signed_amplitude=np.deg2rad(2.0),
        repeat_index=0,
        seed=17002,
        direction_id="+yaw",
        signed_side=1,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("frozen trial invoked a geometric rebuild")

    # Baseline preparation happened above. These functions must not be touched
    # while executing the comparison trial itself.
    monkeypatch.setattr(registration_core, "_query_neighbors", forbidden)
    monkeypatch.setattr(registration_core, "_fit_local_plane", forbidden)
    monkeypatch.setattr(
        registration_core, "_build_point_to_plane_jacobian", forbidden
    )
    result = run_frozen_jacobian_trial(
        snapshot, perturbation, baseline=baseline
    )

    assert result.full_reassociation is False
    assert result.baseline_only is True
    assert result.full_reassociation_count == 0
    assert result.nearest_neighbor_search_count == 0
    assert result.correspondence_build_count == 0
    assert result.plane_fit_count == 0
    assert result.jacobian_recomputation_count == 0
    assert result.transform_count == 0
    assert result.initial_correspondence_count == baseline.correspondence_count
    assert result.final_correspondence_count == baseline.correspondence_count
    assert result.initial_correspondence_checksum == baseline.correspondence_checksum
    assert result.correspondence_checksum == baseline.correspondence_checksum
    assert result.correspondence_checksum_trace == ()


def test_frozen_trial_requires_an_explicitly_prepared_baseline():
    parameter = inspect.signature(run_frozen_jacobian_trial).parameters["baseline"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
