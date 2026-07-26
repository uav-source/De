from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.bounded_branch_reproduction import (
    compare_stage_pair,
    pair_names,
    summarize_semantic_pair,
)
from fastlio2_adapter.day6_semantic_observation import compare_semantic_pair
from test_day6_semantic_observation import record as semantic_record
from test_experiment_a_stage_hash_schema import record as stage_record


def _stage_pair():
    left = [stage_record(scan) for scan in range(135, 161)]
    right = deepcopy(left)
    for row in right:
        row["run_id"] = "right"
    return left, right


def test_four_runs_form_exactly_six_pairs() -> None:
    assert len(pair_names(("r1", "r2", "r3", "r4"))) == 6


def test_traversal_only_is_not_a_formal_branch() -> None:
    left, right = _stage_pair()
    right[2]["map_traversal_before_measurement"] = 999
    right[2]["map_before_traversal_checksum"] = 999
    result = compare_stage_pair(pair="r1-r2", left=left, right=right)
    assert result["stage_classification"] == "NO_FORMAL_DIVERGENCE"
    assert result["formal_branch_reproduced"] is False
    assert result["traversal_difference_observed"] is True


def test_traversal_with_correspondence_is_association_candidate() -> None:
    left, right = _stage_pair()
    right[2]["map_traversal_before_measurement"] = 999
    right[2]["map_before_traversal_checksum"] = 999
    right[2]["formal_correspondence_checksum"] = 999
    result = compare_stage_pair(pair="r1-r2", left=left, right=right)
    assert result["stage_classification"] == (
        "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE"
    )
    assert result["formal_branch_reproduced"] is True


def test_semantic_summary_localizes_and_counts_formal_difference() -> None:
    left = [semantic_record() for _ in range(3)]
    for index, row in enumerate(left):
        row["scan_index"] = index + 3
    right = deepcopy(left)
    right[1]["formal_correspondence_checksum"] = 999
    rows = compare_semantic_pair(pair="r1-r2", left=left, right=right)
    result = summarize_semantic_pair("r1-r2", rows)
    assert result["semantic_mismatch_count"] == 1
    assert result["first_semantic_divergence_record"] == 1
    assert result["first_semantic_divergence_scan"] == 4
    assert result["formal_correspondence_mismatch_count"] == 1

