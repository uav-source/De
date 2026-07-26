from __future__ import annotations

from copy import deepcopy

from fastlio2_adapter.experiment_a_stage_classifier import compare_pair
from test_experiment_a_stage_hash_schema import record


def _pair() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    first = [record(scan) for scan in range(135, 161)]
    for row in first:
        row["run_id"] = "first"
    second = deepcopy(first)
    for row in second:
        row["run_id"] = "second"
    return first, second


def test_all_coherent_no_divergence_keeps_day7_closed() -> None:
    first, second = _pair()
    result = compare_pair(first, second)
    assert result["stage_classification"] == (
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR"
    )
    assert result["day7_recommended"] is False
    assert result["day7_authorized"] is False
    assert result["additional_replay_recommended"] is True
    assert result["additional_replay_authorized"] is False


def test_matched_content_but_traversal_difference_is_separate_stage() -> None:
    first, second = _pair()
    second[3]["map_before_traversal_checksum"] = 999
    second[3]["map_traversal_before_measurement"] = 999
    result = compare_pair(first, second)
    assert result["stage_classification"] == (
        "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT"
    )
    assert result["identity_status"]["map_content_before"] == (
        "MATCHED_BY_CANONICAL_CHECKSUM"
    )


def test_traversal_then_correspondence_difference_recommends_bounded_day7() -> None:
    first, second = _pair()
    second[3]["map_before_traversal_checksum"] = 999
    second[3]["map_traversal_before_measurement"] = 999
    second[3]["formal_correspondence_checksum"] = 999
    result = compare_pair(first, second)
    assert result["day7_recommended"] is True
    assert result["day7_recommended_scope"] == (
        "IKDTREE_TRAVERSAL_ORDER_AND_CORRESPONDENCE_SENSITIVITY"
    )
    assert result["day7_authorized"] is False


def test_map_content_difference_is_map_state_divergence() -> None:
    first, second = _pair()
    for row in second:
        row["map_before_content_checksum"] = 999
        row["map_content_before_measurement"] = 999
        row["map_after_content_checksum"] = 999
        row["map_content_after_insertion"] = 999
    result = compare_pair(first, second)
    assert result["stage_classification"] == "MAP_STATE_ALREADY_DIVERGED"
    assert result["day7_recommended_scope"] == (
        "MAP_MUTATION_AND_IKDTREE_REBUILD_DIAGNOSTICS"
    )
