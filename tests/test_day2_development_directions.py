import math
from pathlib import Path

import numpy as np

from capture_range.day2_development_protocol import (
    EXPECTED_DIRECTION_IDS,
    development_directions,
    load_day2_development_protocol,
    make_perturbation_spec,
)


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_inventory_is_exactly_18_physical_directed_rows():
    directions = development_directions(load_day2_development_protocol(ROOT))
    vectors = np.asarray([row.physical_vector for row in directions])

    assert tuple(row.direction_id for row in directions) == EXPECTED_DIRECTION_IDS
    assert tuple(row.order_index for row in directions) == tuple(range(18))
    assert len(directions) == 18
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1.0e-12)
    dot = vectors @ vectors.T
    assert np.all(dot[~np.eye(18, dtype=bool)] < 0.9999999999)
    assert np.dot(vectors[0], vectors[1]) == -1.0


def test_every_directed_row_adapts_to_canonical_basis_and_signed_side():
    directions = development_directions(load_day2_development_protocol(ROOT))
    for direction in directions:
        spec = make_perturbation_spec(
            direction, "translation", 0.125, repeat_index=0, seed=900_501
        )
        assert spec.direction_id == direction.direction_id
        assert spec.signed_side == direction.signed_side
        assert np.allclose(spec.direction, direction.canonical_basis, atol=0.0)
        assert np.allclose(
            spec.perturbation_vector,
            np.asarray(direction.physical_vector) * 0.125,
            atol=1.0e-15,
        )


def test_zero_amplitude_keeps_antipodal_identity_and_rotation_uses_radians():
    directions = development_directions(load_day2_development_protocol(ROOT))
    negative_x = directions[1]
    zero = make_perturbation_spec(
        negative_x, "translation", 0.0, repeat_index=0, seed=900_501
    )
    radians = math.radians(10.0)
    rotation = make_perturbation_spec(
        negative_x, "rotation", radians, repeat_index=0, seed=900_501
    )

    assert zero.direction_id == "neg_x"
    assert zero.signed_side == -1
    assert zero.signed_amplitude == 0.0
    assert np.allclose(
        rotation.perturbation_vector,
        np.asarray(negative_x.physical_vector) * radians,
        atol=1.0e-15,
    )
