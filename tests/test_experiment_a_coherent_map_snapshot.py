from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.experiment_a_map_snapshot_coherence import (
    pair_coherence_gate,
    records_to_snapshots,
    summarize_snapshots,
)
from fastlio2_adapter.experiment_a_stage_classifier import compare_pair
from test_experiment_a_stage_hash_schema import record


def _pair() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    first = [record(scan) for scan in range(135, 161)]
    for row in first:
        row["run_id"] = "run_1"
    second = deepcopy(first)
    for row in second:
        row["run_id"] = "run_2"
    return first, second


def test_pair_of_twenty_six_records_has_104_coherent_snapshots() -> None:
    first, second = _pair()
    gate = pair_coherence_gate(first, second)
    assert gate["actual_total_snapshot_count"] == 104
    assert gate["coherent_snapshot_count"] == 104
    assert gate["map_snapshot_coherence_pass"] is True


def test_per_run_snapshot_counts_are_26_before_and_26_after() -> None:
    first, _ = _pair()
    assert len(records_to_snapshots(first)) == 52
    summary = summarize_snapshots(first)
    assert summary["map_before_snapshot_count"] == 26
    assert summary["map_after_snapshot_count"] == 26


def test_one_incoherent_before_snapshot_closes_classification() -> None:
    first, second = _pair()
    second[0]["map_before_snapshot_status"] = "GENERATION_CHANGED"
    second[0]["map_before_snapshot_coherence_pass"] = False
    result = compare_pair(first, second)
    assert result["stage_classification"] == (
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT"
    )
    assert result["stage_classification_complete"] is False


def test_one_incoherent_after_snapshot_closes_classification() -> None:
    first, second = _pair()
    second[-1]["map_after_snapshot_status"] = "VALIDNUM_MISMATCH"
    second[-1]["map_after_snapshot_coherence_pass"] = False
    result = compare_pair(first, second)
    assert result["stage_classification"] == (
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT"
    )

