import hashlib
import struct

import pytest

from fastlio2_adapter.day7_map_point_identity import (
    collision_boundary,
    point_identity,
    symmetric_difference,
    validate_identity,
)


def point(**updates):
    value = {
        "x": 1.0,
        "y": 2.0,
        "z": 3.0,
        "intensity": 4.0,
        "normal_x": 5.0,
        "normal_y": 6.0,
        "normal_z": 7.0,
        "curvature": 8.0,
    }
    value.update(updates)
    return value


def test_point_identity_is_canonical_big_endian_sha256():
    expected = hashlib.sha256(struct.pack(">8f", *range(1, 9))).hexdigest()
    assert point_identity(point()) == expected
    assert point_identity(point()) == expected


def test_each_point_field_is_identity_bearing():
    baseline = point_identity(point())
    for field in point():
        assert point_identity(point(**{field: 9.0})) != baseline


def test_identity_validation_and_collision_boundary():
    assert validate_identity("a" * 64) == "a" * 64
    with pytest.raises(ValueError):
        validate_identity("not-a-hash")
    assert "collision" in collision_boundary()


def test_point_set_symmetric_difference_is_canonical():
    assert symmetric_difference(["b", "a"], ["b", "c"]) == (["a"], ["c"])
