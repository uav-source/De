from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.focused_branch_stage_classifier import (
    compare_focused_pair,
)
from test_experiment_a_stage_hash_schema import record


def focused_rows():
    left = [record(scan) for scan in range(155, 206)]
    for row in left:
        row["window_start"] = 155
        row["window_end"] = 205
    right = deepcopy(left)
    for row in right:
        row["run_id"] = "right"
    return left, right


def test_correspondence_branch_at_164_is_localized() -> None:
    left, right = focused_rows()
    right[9]["formal_correspondence_checksum"] = 999
    result = compare_focused_pair(pair="r1-r2", left=left, right=right)
    assert result["first_formal_divergence_scan"] == 164
    assert result["first_formal_divergence_stage"] == (
        "formal_correspondence"
    )
    assert result["stage_classification"] == (
        "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
        "MATCHED_INPUT_AND_MAP_CONTENT"
    )
    assert result["previous_scan_identity_pass"] is True


def test_traversal_and_correspondence_is_association_not_root_proof() -> None:
    left, right = focused_rows()
    right[41]["map_traversal_before_measurement"] = 999
    right[41]["map_before_traversal_checksum"] = 999
    right[41]["formal_native_jacobian_checksum"] = 999
    result = compare_focused_pair(pair="r1-r2", left=left, right=right)
    assert result["first_formal_divergence_scan"] == 196
    assert result["stage_classification"] == (
        "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE"
    )


def test_previous_formal_difference_fails_closed() -> None:
    left, right = focused_rows()
    right[8]["formal_correspondence_checksum"] = 998
    right[9]["formal_correspondence_checksum"] = 999
    result = compare_focused_pair(pair="r1-r2", left=left, right=right)
    assert result["first_formal_divergence_scan"] == 163
