from __future__ import annotations

from fastlio2_adapter.experiment_a_map_snapshot_coherence import (
    cross_scan_continuity,
)
from test_experiment_a_stage_hash_schema import record


def _records() -> list[dict[str, object]]:
    return [record(scan) for scan in range(135, 161)]


def test_no_mutation_requires_content_and_count_identity() -> None:
    rows, summary = cross_scan_continuity(_records())
    assert len(rows) == 25
    assert summary["violation_count"] == 0


def test_no_mutation_content_change_is_violation() -> None:
    records = _records()
    records[1]["map_before_content_checksum"] = 999
    rows, summary = cross_scan_continuity(records)
    assert rows[0]["continuity_pass"] is False
    assert summary["violation_count"] == 1


def test_no_add_but_count_increase_is_violation() -> None:
    records = _records()
    records[1]["map_before_snapshot_point_count"] = 1575
    records[1]["map_before_validnum_before"] = 1575
    records[1]["map_before_validnum_after"] = 1575
    rows, summary = cross_scan_continuity(records)
    assert rows[0]["continuity_rule"] == "NO_ADD_FORBIDS_COUNT_INCREASE"
    assert summary["map_snapshot_cross_scan_coherence_pass"] is False


def test_596_to_1575_without_add_regression_fixture_fails() -> None:
    records = _records()
    records[0]["map_after_snapshot_point_count"] = 596
    records[1]["map_before_snapshot_point_count"] = 1575
    rows, _ = cross_scan_continuity(records)
    assert rows[0]["previous_after_count"] == 596
    assert rows[0]["current_before_count"] == 1575
    assert rows[0]["continuity_pass"] is False


def test_generation_and_traversal_change_with_same_content_is_allowed() -> None:
    records = _records()
    records[1]["map_before_rebuild_generation_before"] = 2
    records[1]["map_before_rebuild_generation_after"] = 2
    records[1]["map_before_traversal_checksum"] = 123456
    rows, summary = cross_scan_continuity(records)
    assert rows[0]["rebuild_generation_delta"] == 1
    assert rows[0]["continuity_pass"] is True
    assert summary["violation_count"] == 0

