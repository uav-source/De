from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.day6_semantic_observation import compare_semantic_pair
from fastlio2_adapter.focused_branch_stage_localization import (
    summarize_full_stream,
)
from test_day6_semantic_observation import record


def test_full_stream_summary_localizes_measurement_before_prior() -> None:
    left = [record() for _ in range(200)]
    for index, row in enumerate(left):
        row["scan_index"] = index + 3
        row["measurement_call_index"] = index
    right = deepcopy(left)
    right[161]["formal_correspondence_checksum"] = 999
    right[162]["prior_position_world"] = [1.0, 0.0, 0.0]
    rows = compare_semantic_pair(pair="r1-r2", left=left, right=right)
    summary = summarize_full_stream("r1-r2", rows)
    assert summary["first_divergence_record"] == 161
    assert summary["first_divergence_scan"] == 164
    assert summary["first_correspondence_divergence"]["scan_index"] == 164
    assert summary["first_prior_state_divergence"]["scan_index"] == 165


def test_identity_only_difference_is_excluded() -> None:
    left = [record()]
    right = deepcopy(left)
    right[0]["run_id"] = "different"
    rows = compare_semantic_pair(pair="r1-r2", left=left, right=right)
    assert summarize_full_stream(
        "r1-r2", rows
    )["semantic_mismatch_count"] == 0

