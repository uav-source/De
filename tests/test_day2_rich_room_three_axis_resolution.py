from pathlib import Path

from capture_range.day2_protocol import (
    load_effective_day2_protocol,
    resolve_all_scene_directions,
)


ROOT = Path(__file__).resolve().parents[1]
YZ_AXES = ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_rich_room_preserves_all_three_control_axes_without_selecting_two():
    effective = load_effective_day2_protocol(ROOT)
    contract = effective.amendment["direction_inventory_resolution"]
    rich = resolve_all_scene_directions(effective)["GEOMETRY_RICH_ROOM"]
    controls = [
        row for row in rich.declarations if row.role == "rich_room_control_axis"
    ]

    assert contract["geometry_rich_room_declared_strong_axes_count"] == 3
    assert contract["geometry_rich_room"]["declared_strong_axes"] == (
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
    )
    assert contract["geometry_rich_room"]["all_three_are_control_axes"] is True
    assert contract["geometry_rich_room"]["no_arbitrary_selection_of_two_axes"] is True
    assert contract["geometry_rich_room_role"] == (
        "control_only_not_strong_weak_separation_gate"
    )
    assert len(controls) == 6
    assert {row.retained_direction_id for row in controls} == {
        "pos_x", "neg_x", "pos_y", "neg_y", "pos_z", "neg_z",
    }
    assert all(row.alias_of == row.retained_direction_id for row in controls)


def test_each_degraded_scene_keeps_exactly_y_and_z_as_strong_axes():
    effective = load_effective_day2_protocol(ROOT)
    strong_axes = effective.amendment["direction_inventory_resolution"][
        "degraded_scenes"
    ]["strong_axes_for_separation"]

    assert tuple(strong_axes) == (
        "LONG_CORRIDOR",
        "PARALLEL_WALLS",
        "END_FACE_TRANSITION_WEAK",
        "END_FACE_TRANSITION_ABSENT",
        "REPEATED_STRUCTURE",
    )
    assert all(tuple(tuple(axis) for axis in axes) == YZ_AXES for axes in strong_axes.values())

    resolutions = resolve_all_scene_directions(effective)
    for scene_key in strong_axes:
        strong = [
            row
            for row in resolutions[scene_key].declarations
            if row.role == "scene_strong_axis"
        ]
        assert len(strong) == 4
        assert {row.retained_direction_id for row in strong} == {
            "pos_y", "neg_y", "pos_z", "neg_z",
        }
