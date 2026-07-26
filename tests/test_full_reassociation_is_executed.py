from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree

from capture_range import registration_core
from capture_range.full_reassociation_runner import run_full_reassociation_trial
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


def test_full_path_executes_every_geometric_pass_for_each_evaluation(monkeypatch):
    snapshot = _rich_snapshot()
    perturbation = PerturbationSpec(
        perturbation_type="translation",
        direction=np.array([1.0, 0.0, 0.0]),
        signed_amplitude=0.10,
        repeat_index=0,
        seed=17001,
        direction_id="+x",
        signed_side=1,
    )
    query_calls = 0
    original_query = registration_core._query_neighbors

    def counted_query(*args, **kwargs):
        nonlocal query_calls
        query_calls += 1
        return original_query(*args, **kwargs)

    monkeypatch.setattr(registration_core, "_query_neighbors", counted_query)
    result = run_full_reassociation_trial(snapshot, perturbation)

    assert result.full_reassociation is True
    assert result.baseline_only is False
    assert result.solver_converged is True
    assert result.full_reassociation_count == result.iteration_count + 1
    assert result.full_reassociation_count >= 2  # initial/iterated plus final
    assert query_calls == result.full_reassociation_count
    assert result.transform_count == result.full_reassociation_count
    assert result.nearest_neighbor_search_count == result.full_reassociation_count
    assert result.correspondence_build_count == result.full_reassociation_count
    assert result.plane_fit_count == result.full_reassociation_count
    assert result.jacobian_recomputation_count == result.full_reassociation_count
    assert result.initial_correspondence_count > 0
    assert result.final_correspondence_count > 0
    assert result.correspondence_checksum
    assert len(result.correspondence_checksum_trace) == result.full_reassociation_count
    assert result.correspondence_checksum_trace[0] == result.initial_correspondence_checksum
    assert result.correspondence_checksum_trace[-1] == result.correspondence_checksum


def test_knn_boundary_ties_are_selected_by_stable_map_index():
    local_map = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ]
    )
    distances, indices = registration_core._query_neighbors(
        cKDTree(local_map), np.zeros((1, 3)), 3
    )

    np.testing.assert_array_equal(indices[0], [0, 1, 2])
    np.testing.assert_array_equal(distances[0], [1.0, 1.0, 1.0])
