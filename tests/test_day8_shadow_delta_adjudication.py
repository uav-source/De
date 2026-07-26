from fastlio2_adapter.day8_shadow_voxel_replay import (
    apply_mutation,
    flatten_shadow,
)


def test_replacement_full_voxel_delta_uses_one_minus_member_count():
    voxel = "0" * 48
    a, b, selected = "a" * 64, "b" * 64, "c" * 64
    state = {voxel: {a, b}}
    delta = apply_mutation(
        state,
        {
            "formal_outcome": "REPLACED_EXISTING_VOXEL_REPRESENTATIVE",
            "candidate_point_sha256": selected,
            "selected_representative_sha256": selected,
            "voxel_identity": voxel,
            "logical_point_count_delta_claimed": 0,
        },
        {a: voxel, b: voxel, selected: voxel},
    )
    assert delta == -1
    assert flatten_shadow(state) == {selected}
