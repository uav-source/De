import csv
import json
from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.scene_generator import (  # noqa: E402
    generate_curved_tunnel,
    generate_open_control,
    generate_repetitive_tunnel,
    generate_straight_tunnel,
    load_scene_config,
    save_sequence,
)


def config(name):
    return load_scene_config(ROOT / "configs" / "minibench" / name)


def plane_normals(sequence):
    return np.array([plane.normal for plane in sequence.planes])


def assert_unit_rows(values, atol=1.0e-8):
    norms = np.linalg.norm(values, axis=1)
    assert np.allclose(norms, 1.0, atol=atol)


def test_generated_frame_counts_match_configs():
    cases = [
        ("OC-L0-S01-M1.yaml", generate_open_control),
        ("ST-L3-S01-M1.yaml", generate_straight_tunnel),
        ("CT-L2-S01-M2.yaml", generate_curved_tunnel),
        ("RT-L4-S01-M1.yaml", generate_repetitive_tunnel),
    ]
    for name, generator in cases:
        cfg = config(name)
        sequence = generator(cfg)

        assert sequence.gt_poses.shape == (cfg["frames"], 8)
        assert sequence.axis.shape == (cfg["frames"], 3)
        assert sequence.metadata["frames"] == cfg["frames"]


def test_axes_are_unit_length():
    cases = [
        generate_open_control(config("OC-L0-S01-M1.yaml")),
        generate_straight_tunnel(config("ST-L3-S01-M1.yaml")),
        generate_curved_tunnel(config("CT-L2-S01-M2.yaml")),
        generate_repetitive_tunnel(config("RT-L4-S01-M1.yaml")),
    ]

    for sequence in cases:
        assert_unit_rows(sequence.axis)


def test_straight_tunnel_normals_preserve_x_axis_weakness():
    sequence = generate_straight_tunnel(config("ST-L3-S01-M1.yaml"))
    normals = plane_normals(sequence)

    assert np.mean(np.abs(normals[:, 0]) < 0.05) >= 0.95
    assert np.max(np.abs(normals[:, 0])) == 0.0


def test_repetitive_tunnel_normals_preserve_x_axis_weakness():
    sequence = generate_repetitive_tunnel(config("RT-L4-S01-M1.yaml"))
    normals = plane_normals(sequence)

    assert np.mean(np.abs(normals[:, 0]) < 0.05) >= 0.95
    assert np.max(np.abs(normals[:, 0])) == 0.0
    assert len(sequence.planes) > 4


def test_open_control_normals_are_not_single_direction_concentrated():
    sequence = generate_open_control(config("OC-L0-S01-M1.yaml"))
    normals = plane_normals(sequence)

    mean_norm = np.linalg.norm(np.mean(normals, axis=0))
    covariance = normals.T @ normals / normals.shape[0]
    eigvals = np.linalg.eigvalsh(covariance)

    assert mean_norm < 0.15
    assert eigvals.min() > 0.20
    assert eigvals.max() / eigvals.min() < 2.0


def test_save_sequence_writes_required_files_and_metadata(tmp_path):
    cfg = config("ST-L3-S01-M1.yaml")
    sequence = generate_straight_tunnel(cfg)
    save_sequence(sequence, tmp_path)

    for filename in ["gt.tum", "axis.csv", "planes.csv", "scene_metadata.json", "feature_points.csv"]:
        assert (tmp_path / filename).is_file()

    metadata = json.loads((tmp_path / "scene_metadata.json").read_text(encoding="utf-8"))
    assert metadata["config_sha256"]
    assert metadata["random_seed"] == 42
    assert metadata["expected_degeneracy"] == "high_axis_translation"
    assert metadata["generated_by"] == "scripts/00_generate_minibench.py"


def test_saved_csv_row_counts_match_frames_and_planes(tmp_path):
    cfg = config("RT-L4-S01-M1.yaml")
    sequence = generate_repetitive_tunnel(cfg)
    save_sequence(sequence, tmp_path)

    gt = np.loadtxt(tmp_path / "gt.tum")
    assert gt.shape == (cfg["frames"], 8)

    with (tmp_path / "axis.csv").open("r", encoding="utf-8") as handle:
        axis_rows = list(csv.DictReader(handle))
    assert len(axis_rows) == cfg["frames"]

    with (tmp_path / "planes.csv").open("r", encoding="utf-8") as handle:
        plane_rows = list(csv.DictReader(handle))
    assert len(plane_rows) == len(sequence.planes)

