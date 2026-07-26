from pathlib import Path

import numpy as np

from capture_range.day2_protocol import (
    SCENE_VARIANT_ORDER,
    load_effective_day2_protocol,
    resolve_all_scene_directions,
)


ROOT = Path(__file__).resolve().parents[1]


def test_declarations_and_retained_directions_are_separate_collections():
    effective = load_effective_day2_protocol(ROOT)
    resolutions = resolve_all_scene_directions(effective)
    expected_declaration_counts = {
        "GEOMETRY_RICH_ROOM": 24,
        "LONG_CORRIDOR": 24,
        "PARALLEL_WALLS": 24,
        "END_FACE_TRANSITION_PRESENT": 22,
        "END_FACE_TRANSITION_WEAK": 24,
        "END_FACE_TRANSITION_ABSENT": 24,
        "REPEATED_STRUCTURE": 24,
    }

    assert tuple(resolutions) == SCENE_VARIANT_ORDER
    assert {
        key: len(value.declarations) for key, value in resolutions.items()
    } == expected_declaration_counts
    assert sum(len(value.declarations) for value in resolutions.values()) == 166
    assert all(len(value.retained_directions) == 18 for value in resolutions.values())
    assert sum(len(value.retained_directions) for value in resolutions.values()) == 126


def test_aliases_preserve_roles_and_base_source_precedence():
    effective = load_effective_day2_protocol(ROOT)
    resolutions = resolve_all_scene_directions(effective)

    for resolution in resolutions.values():
        retained = {row.direction_id: row for row in resolution.retained_directions}
        for declaration in resolution.declarations:
            if declaration.role in {
                "scene_weak_axis", "scene_strong_axis", "rich_room_control_axis",
            }:
                assert declaration.alias_of == declaration.retained_direction_id
                assert retained[declaration.alias_of].direction_source == (
                    "base_directed_axis"
                )
        assert sum(row.alias_of is not None for row in resolution.declarations) in {
            4, 6,
        }


def test_antipodal_directions_are_never_merged_by_absolute_dot():
    effective = load_effective_day2_protocol(ROOT)
    resolutions = resolve_all_scene_directions(effective)

    for resolution in resolutions.values():
        retained = {row.direction_id: row for row in resolution.retained_directions}
        for positive, negative in (
            ("pos_x", "neg_x"), ("pos_y", "neg_y"), ("pos_z", "neg_z"),
        ):
            assert positive in retained and negative in retained
            assert np.dot(
                retained[positive].normalized_vector,
                retained[negative].normalized_vector,
            ) == -1.0
        vectors = np.asarray(
            [row.normalized_vector for row in resolution.retained_directions]
        )
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1.0e-12)
