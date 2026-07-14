from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.scene_generator import (  # noqa: E402
    build_axial_support_patches,
    build_rectangular_tunnel_patches,
    set_sampling_fraction,
)


def axial_information(fraction):
    rng = np.random.default_rng(101)
    planes = build_rectangular_tunnel_patches(60, 30.0, 4.0, 3.0)
    planes.extend(build_axial_support_patches(30.0, 4.0, 3.0, 8, fraction, rng, frames=60))
    set_sampling_fraction(planes, fraction)
    return sum(plane.sampling_weight * float(plane.normal[0] ** 2) for plane in planes)


def test_axial_support_geometry_is_strictly_ordered():
    values = [axial_information(value) for value in [0.25, 0.10, 0.03, 0.005]]
    assert values[0] > values[1] > values[2] > values[3] > 0.0


def test_geometry_seed_is_reproducible_and_changes_geometry():
    first = build_axial_support_patches(30.0, 4.0, 3.0, 8, 0.10, np.random.default_rng(101), frames=60)
    same = build_axial_support_patches(30.0, 4.0, 3.0, 8, 0.10, np.random.default_rng(101), frames=60)
    different = build_axial_support_patches(30.0, 4.0, 3.0, 8, 0.10, np.random.default_rng(202), frames=60)
    assert np.allclose([plane.point for plane in first], [plane.point for plane in same])
    assert not np.allclose([plane.point for plane in first], [plane.point for plane in different])

