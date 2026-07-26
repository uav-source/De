from fastlio2_adapter.day7_map_update_root_cause import (
    classify_event_difference,
    classify_pair_components,
)


def base_event(**updates):
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


def test_logger_apply_order_class():
    assert classify_pair_components(
        map_diverged=True,
        left_event=None,
        right_event=None,
        logger={
            "append_multiset_equal": True,
            "apply_order_equal": False,
            "apply_result_equal": False,
        },
    ) == "REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED"


def test_logger_apply_result_class():
    assert classify_pair_components(
        map_diverged=True,
        left_event=None,
        right_event=None,
        logger={
            "append_multiset_equal": True,
            "apply_order_equal": True,
            "apply_result_equal": False,
        },
    ) == "REBUILD_LOGGER_APPLICATION_RESULT_DIVERGED"


def test_delete_reinsert_interaction_class():
    assert classify_event_difference(
        base_event(formal_outcome="DELETED_BY_BOX"),
        base_event(formal_outcome="DELETE_BOX_NO_MATCH"),
    ) == "DELETE_OR_REINSERTION_INTERACTION_DIVERGED"


def test_no_branch_structured_end():
    assert classify_pair_components(
        map_diverged=False,
        left_event=None,
        right_event=None,
        logger={},
    ) == "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED"


def test_timing_does_not_prove_data_race():
    classification = classify_pair_components(
        map_diverged=True,
        left_event=None,
        right_event=None,
        logger={
            "append_multiset_equal": True,
            "apply_order_equal": False,
            "apply_result_equal": False,
        },
    )
    assert classification == "REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED"
    assert classification != "DATA_RACE_PROVEN"
