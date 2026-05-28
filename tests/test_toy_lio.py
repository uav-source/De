from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.toy_lio import run_toy_lio, save_pose_est_tum  # noqa: E402


CONFIG = ROOT / "configs/detector/odi_default.yaml"


def seq(name):
    return ROOT / "data/minibench" / name


def load_gt(sequence_id):
    return np.loadtxt(seq(sequence_id) / "gt.tum")


def assert_tum_format(poses):
    assert poses.ndim == 2
    assert poses.shape[1] == 8
    assert np.all(np.isfinite(poses))
    quat_norm = np.linalg.norm(poses[:, 4:8], axis=1)
    assert np.allclose(quat_norm, 1.0, atol=1.0e-6)


def test_output_pose_count_matches_gt_and_tum_format(tmp_path):
    result = run_toy_lio(seq("ST-L3-S01-M1"), CONFIG)
    poses = result["poses"]
    gt = load_gt("ST-L3-S01-M1")

    assert poses.shape[0] == gt.shape[0]
    assert_tum_format(poses)

    out = tmp_path / "pose_est_toy.tum"
    save_pose_est_tum(poses, out)
    loaded = np.loadtxt(out)
    assert loaded.shape == poses.shape


def test_open_control_does_not_obviously_diverge():
    result = run_toy_lio(seq("OC-L0-S01-M1"), CONFIG)
    summary = result["summary"]

    assert summary["final_translation_error"] < 0.75
    assert summary["mean_axis_error"] < 0.25


def test_straight_tunnel_axis_error_exceeds_cross_error():
    result = run_toy_lio(seq("ST-L3-S01-M1"), CONFIG)
    summary = result["summary"]

    assert summary["final_axis_error"] > 2.0 * summary["final_cross_error"]
    assert summary["mean_axis_error"] > 2.0 * summary["mean_cross_error"]


def test_repetitive_tunnel_axis_error_exceeds_cross_error():
    result = run_toy_lio(seq("RT-L4-S01-M1"), CONFIG)
    summary = result["summary"]

    assert summary["final_axis_error"] > 2.0 * summary["final_cross_error"]
    assert summary["mean_axis_error"] > 2.0 * summary["mean_cross_error"]


def test_result_is_reproducible_with_fixed_seed():
    first = run_toy_lio(seq("CT-L2-S01-M2"), CONFIG)["poses"]
    second = run_toy_lio(seq("CT-L2-S01-M2"), CONFIG)["poses"]

    assert np.allclose(first, second)


def test_toy_lio_source_does_not_depend_on_detector_csv():
    source_raw = (ROOT / "src/minibench/toy_lio.py").read_text(encoding="utf-8")
    source = source_raw.lower()

    assert "_odi" not in source
    assert "odi.csv" not in source
    assert "ODI" not in source_raw
    assert "results/day14/raw" not in source
