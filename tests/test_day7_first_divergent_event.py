from fastlio2_adapter.day7_map_update_root_cause import (
    classify_event_difference,
    classify_pair_components,
)


def event(**updates):
    value = {
        "candidate_point_sha256": "a" * 64,
        "voxel_identity": "0" * 48,
        "existing_representative_sha256": "b" * 64,
        "selected_representative_sha256": "a" * 64,
        "decision_context_ordered_checksum": 1,
        "formal_outcome": "INSERTED_NEW_VOXEL_REPRESENTATIVE",
        "mutation_destination": "DIRECT_TREE",
    }
    value.update(updates)
    return value


def test_candidate_outcome_difference_is_localized():
    right = event(formal_outcome="REPLACED_EXISTING_VOXEL_REPRESENTATIVE")
    assert classify_event_difference(event(), right) == (
        "DIRECT_TREE_INSERTION_OUTCOME_DIVERGED"
    )


def test_representative_selection_difference_is_localized():
    right = event(selected_representative_sha256="c" * 64)
    assert classify_event_difference(event(), right) == (
        "VOXEL_REPRESENTATIVE_SELECTION_DIVERGED"
    )


def test_direct_logger_routing_difference_is_localized():
    right = event(mutation_destination="BOTH")
    assert classify_event_difference(event(), right) == (
        "REBUILD_LOGGER_ROUTING_DIVERGED"
    )


def test_same_events_different_map_after_is_evidence_gap_class():
    assert classify_pair_components(
        map_diverged=True,
        left_event=None,
        right_event=None,
        logger={
            "append_multiset_equal": True,
            "apply_order_equal": True,
            "apply_result_equal": True,
        },
    ) == "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER"
