import csv
from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.observation_simulator import load_planes_csv, sample_points_on_planes  # noqa: E402
from minibench.scene_generator import PlanePatch, save_planes_csv  # noqa: E402


def patch():
    return PlanePatch(
        "finite",
        0,
        10,
        np.array([1.0, 0.0, 0.0]),
        np.array([2.0, 0.0, 0.0]),
        "test",
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        0.7,
        0.4,
    )


def test_finite_patch_samples_stay_inside_bounds():
    plane = patch()
    points, _ = sample_points_on_planes(np.zeros(3), [plane], 1000, np.random.default_rng(5))
    relative = points - plane.point
    assert np.max(np.abs(relative @ plane.u_axis)) <= plane.half_u + 1.0e-12
    assert np.max(np.abs(relative @ plane.v_axis)) <= plane.half_v + 1.0e-12
    assert np.max(np.abs(relative @ plane.normal)) <= 1.0e-12
    assert abs(float(plane.normal @ plane.u_axis)) < 1.0e-12
    assert abs(float(plane.normal @ plane.v_axis)) < 1.0e-12
    assert abs(float(plane.u_axis @ plane.v_axis)) < 1.0e-12


def test_old_and_new_plane_csv_are_readable(tmp_path):
    old_path = tmp_path / "old.csv"
    with old_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["plane_id", "frame_start", "frame_end", "nx", "ny", "nz", "qx", "qy", "qz", "semantic"])
        writer.writerow(["legacy", 0, 9, 0, 1, 0, 0, 2, 0, "wall"])
    old = load_planes_csv(old_path)
    assert len(old) == 1
    assert old[0].half_u == 1000.0

    new_path = tmp_path / "new.csv"
    save_planes_csv(new_path, [patch()])
    new = load_planes_csv(new_path)
    assert len(new) == 1
    assert np.allclose(new[0].u_axis, patch().u_axis)
    assert np.allclose(new[0].v_axis, patch().v_axis)
    assert new[0].half_u == patch().half_u
    assert new[0].half_v == patch().half_v

