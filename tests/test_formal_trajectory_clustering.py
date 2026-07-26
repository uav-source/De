from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.formal_trajectory_clustering import (
    cluster_formal_trajectories,
)
from test_day6_semantic_observation import record


def _trajectory(run_id: str):
    rows = [record() for _ in range(487)]
    for index, row in enumerate(rows):
        row["run_id"] = run_id
        row["scan_index"] = index + 3
        row["measurement_call_index"] = index
    return rows


def test_identity_only_changes_remain_one_cluster() -> None:
    observations = {
        run_id: _trajectory(run_id)
        for run_id in ("r1", "r2", "r3", "r4")
    }
    result = cluster_formal_trajectories(observations)
    assert result["cluster_count"] == 1
    assert result["unique_formal_trajectory_count"] == 1
    assert all(row["same_formal_trajectory"] for row in result["pairs"])


def test_formal_change_creates_a_second_cluster() -> None:
    base = _trajectory("r1")
    observations = {
        "r1": base,
        "r2": deepcopy(base),
        "r3": deepcopy(base),
        "r4": deepcopy(base),
    }
    observations["r4"][100]["formal_filter_innovation_h"] = [999.0]
    result = cluster_formal_trajectories(observations)
    assert result["cluster_count"] == 2
    assert result["unique_formal_trajectory_count"] == 2

