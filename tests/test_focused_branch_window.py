from __future__ import annotations

import fastlio2_adapter.experiment_a_map_snapshot_coherence as snapshots
import fastlio2_adapter.experiment_a_stage_hash as stage_hash
from fastlio2_adapter.focused_branch_stage_classifier import (
    EXPECTED_RECORD_COUNT,
    EXPECTED_SNAPSHOTS_PER_RUN,
    SCAN_END,
    SCAN_START,
    focused_contract,
)


def test_focused_window_is_fixed_and_inclusive() -> None:
    assert (SCAN_START, SCAN_END) == (155, 205)
    assert EXPECTED_RECORD_COUNT == 51
    assert EXPECTED_SNAPSHOTS_PER_RUN == 102
    original_stage_window = (stage_hash.SCAN_START, stage_hash.SCAN_END)
    original_snapshot_count = snapshots.EXPECTED_SNAPSHOTS_PER_RUN
    with focused_contract():
        assert stage_hash.SCAN_START == 155
        assert stage_hash.SCAN_END == 205
        assert stage_hash.EXPECTED_RECORD_COUNT == 51
        assert snapshots.EXPECTED_SNAPSHOTS_PER_RUN == 102
    assert (stage_hash.SCAN_START, stage_hash.SCAN_END) == (
        original_stage_window
    )
    assert snapshots.EXPECTED_SNAPSHOTS_PER_RUN == original_snapshot_count


def test_focused_window_covers_both_prior_branch_scans() -> None:
    scans = set(range(SCAN_START, SCAN_END + 1))
    assert {164, 196}.issubset(scans)
