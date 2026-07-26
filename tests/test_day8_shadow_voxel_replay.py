import pytest

from fastlio2_adapter.day8_shadow_voxel_replay import (
    apply_mutation,
    flatten_shadow,
    initialize_shadow,
    replay_scan,
)


VOXEL_A = "0" * 48
VOXEL_B = "1" * 48
POINT_A = "a" * 64
POINT_B = "b" * 64
POINT_C = "c" * 64


def _event(outcome, candidate, selected, delta, index=1):
    return {
        "formal_outcome": outcome, "candidate_point_sha256": candidate,
        "selected_representative_sha256": selected,
        "existing_representative_sha256": "",
        "voxel_identity": VOXEL_A, "logical_point_count_delta_claimed": delta,
        "call_index": 1, "batch_point_index": index,
        "event_sequence": index,
    }


def test_shadow_initialization_replacement_insertion_and_delete():
    state = initialize_shadow([(POINT_A, VOXEL_A)])
    apply_mutation(
        state,
        _event(
            "REPLACED_EXISTING_VOXEL_REPRESENTATIVE", POINT_B, POINT_B, 0
        ),
        {POINT_A: VOXEL_A, POINT_B: VOXEL_A, POINT_C: VOXEL_B},
    )
    assert flatten_shadow(state) == {POINT_B}
    inserted = _event(
        "INSERTED_NEW_VOXEL_REPRESENTATIVE", POINT_C, POINT_C, 1, 2
    )
    inserted["voxel_identity"] = VOXEL_B
    apply_mutation(
        state, inserted,
        {POINT_A: VOXEL_A, POINT_B: VOXEL_A, POINT_C: VOXEL_B},
    )
    assert flatten_shadow(state) == {POINT_B, POINT_C}
    deleted = _event("DELETED_BY_BOX", POINT_B, "", -1, 3)
    deleted["existing_representative_sha256"] = POINT_B
    apply_mutation(
        state, deleted,
        {POINT_A: VOXEL_A, POINT_B: VOXEL_A, POINT_C: VOXEL_B},
    )
    assert flatten_shadow(state) == {POINT_C}


def test_shadow_delta_or_map_after_mismatch_fails():
    state = initialize_shadow([(POINT_A, VOXEL_A)])
    bad = _event("REJECTED_EXISTING_REPRESENTATIVE_CLOSER", POINT_B, "", 1)
    with pytest.raises(ValueError, match="delta"):
        apply_mutation(state, bad, {POINT_A: VOXEL_A, POINT_B: VOXEL_A})
    with pytest.raises(ValueError, match="MAP_AFTER"):
        replay_scan(
            run_id="r1", before_pairs=[(POINT_A, VOXEL_A)],
            after_pairs=[(POINT_B, VOXEL_A)], queries=[], events=[],
            known_pairs={POINT_A: VOXEL_A, POINT_B: VOXEL_A},
        )


def test_shadow_allows_formal_insertion_into_logically_occupied_voxel():
    state = initialize_shadow([(POINT_A, VOXEL_A)])
    apply_mutation(
        state,
        _event(
            "INSERTED_NEW_VOXEL_REPRESENTATIVE", POINT_B, POINT_B, 1
        ),
        {POINT_A: VOXEL_A, POINT_B: VOXEL_A},
    )
    assert flatten_shadow(state) == {POINT_A, POINT_B}


def test_tolerant_shadow_records_delta_accounting_gap_and_closes():
    event = _event(
        "REPLACED_EXISTING_VOXEL_REPRESENTATIVE", POINT_C, POINT_C, 0
    )
    rows = replay_scan(
        run_id="r1",
        before_pairs=[(POINT_A, VOXEL_A), (POINT_B, VOXEL_A)],
        after_pairs=[(POINT_C, VOXEL_A)],
        queries=[{
            "scan_index": 155, "map_mutation_call_index": 1,
            "batch_point_index": 1, "query_sequence": 1,
            "candidate_point_sha256": POINT_C,
            "voxel_identity": VOXEL_A,
            "formal_result_members": (POINT_A,),
        }],
        events=[event],
        known_pairs={
            POINT_A: VOXEL_A, POINT_B: VOXEL_A, POINT_C: VOXEL_A,
        },
        tolerate_accounting_failure=True,
    )
    assert rows[0]["shadow_mutation_delta_failure_count"] == 1
    assert rows[0]["shadow_state_closure_failure_count"] == 0
    assert rows[0]["shadow_state_accounting_pass"] == 0
