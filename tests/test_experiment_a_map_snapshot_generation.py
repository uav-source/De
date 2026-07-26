from __future__ import annotations

import pytest

from fastlio2_adapter.experiment_a_map_snapshot_coherence import (
    MapSnapshotCoherenceError,
    snapshot_from_record,
    validate_snapshot,
)
from test_experiment_a_stage_hash_schema import record


def test_stable_generation_and_mutation_counter_pass() -> None:
    snapshot = snapshot_from_record(record(135), "map_before")
    assert validate_snapshot(snapshot)["snapshot_coherence_pass"] is True


def test_generation_change_fails_closed() -> None:
    value = record(135)
    value["map_before_rebuild_generation_after"] = 2
    with pytest.raises(MapSnapshotCoherenceError, match="generation"):
        validate_snapshot(snapshot_from_record(value, "map_before"))


def test_mutation_counter_change_fails_closed() -> None:
    value = record(135)
    value["map_after_mutation_counter_after"] = 2
    with pytest.raises(MapSnapshotCoherenceError, match="mutation"):
        validate_snapshot(snapshot_from_record(value, "map_after"))


def test_retry_attempt_count_is_bounded_to_three() -> None:
    value = record(135)
    value["map_before_snapshot_attempt_count"] = 4
    with pytest.raises(MapSnapshotCoherenceError, match="attempt"):
        validate_snapshot(snapshot_from_record(value, "map_before"))

