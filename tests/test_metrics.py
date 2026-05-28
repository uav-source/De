import csv
import importlib.util
from pathlib import Path

import numpy as np
import pytest

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metrics import (  # noqa: E402
    align_se3_if_needed,
    compute_ATE,
    compute_axis_error,
    compute_cross_error,
    compute_cumulative_path_length,
    compute_sliding_window_drift_rate,
    load_axis_csv,
    load_tum_pose,
)


def make_poses(positions):
    positions = np.asarray(positions, dtype=float)
    timestamps = np.arange(positions.shape[0], dtype=float)
    quat = np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (positions.shape[0], 1))
    return np.column_stack([timestamps, positions, quat])


def test_metrics_contract_includes_directional_and_alternative_metrics():
    text = (ROOT / "docs/metrics_contract.md").read_text(encoding="utf-8")

    assert "e_axis(t) = |a(t)^T (p_est(t) - p_gt(t))|" in text
    assert "e_cross(t) = ||(I - a(t)a(t)^T)(p_est(t) - p_gt(t))||_2" in text
    assert "ODI" in text
    assert "condition_number" in text
    assert "lambda_min" in text
    assert "AIS" in text


def test_day14_acceptance_freezes_gate_thresholds():
    text = (ROOT / "docs/day14_acceptance.md").read_text(encoding="utf-8")

    assert "Median reliable axis alignment >= 0.70" in text
    assert "Spearman rho(ODI, axis drift rate) >= 0.50" in text
    assert "ODI beats condition_number or lambda_min" in text


def test_tum_file_reading_is_correct(tmp_path):
    tum_path = tmp_path / "pose.tum"
    tum_path.write_text(
        "0.0 1.0 2.0 3.0 0.0 0.0 0.0 2.0\n"
        "0.1 2.0 3.0 4.0 0.0 0.0 0.0 1.0\n",
        encoding="utf-8",
    )

    poses = load_tum_pose(tum_path)

    assert poses.shape == (2, 8)
    assert np.allclose(poses[:, 0], [0.0, 0.1])
    assert np.allclose(np.linalg.norm(poses[:, 4:8], axis=1), 1.0)


def test_axis_csv_loading_normalizes_rows(tmp_path):
    axis_path = tmp_path / "axis.csv"
    axis_path.write_text(
        "timestamp,axis_x,axis_y,axis_z,reliable\n"
        "0.0,2.0,0.0,0.0,1\n"
        "0.1,0.0,3.0,0.0,1\n",
        encoding="utf-8",
    )

    axis = load_axis_csv(axis_path)

    assert axis.shape == (2, 3)
    assert np.allclose(np.linalg.norm(axis, axis=1), 1.0)


def test_axis_cross_decomposition_and_signed_projection_are_correct():
    gt = make_poses([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    est = make_poses([[-2.0, 3.0, 0.0], [0.0, 2.0, -4.0]])
    axis = np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0]], dtype=float)

    axis_error = compute_axis_error(est, gt, axis)
    cross_error = compute_cross_error(est, gt, axis)

    assert np.allclose(axis_error, [2.0, 4.0])
    assert np.allclose(cross_error, [3.0, 2.0])

    error = est[:, 1:4] - gt[:, 1:4]
    signed = np.einsum("ij,ij->i", error, axis)
    cross_vec = error - signed[:, None] * axis
    assert np.allclose(np.einsum("ij,ij->i", cross_vec, axis), 0.0)


def test_zero_error_makes_ate_axis_and_cross_zero():
    gt = make_poses([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    est = gt.copy()
    axis = np.asarray([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float)

    assert compute_ATE(est, gt) == pytest.approx(0.0)
    assert np.allclose(compute_axis_error(est, gt, axis), 0.0)
    assert np.allclose(compute_cross_error(est, gt, axis), 0.0)


def test_sliding_window_count_and_rate_are_correct():
    error = np.arange(10, dtype=float)
    path_length = 2.0 * np.arange(10, dtype=float)

    windows = compute_sliding_window_drift_rate(error, path_length, window_size=4, stride=3)

    assert windows.shape[0] == 3
    assert np.all(windows["start_idx"] == [0, 3, 6])
    assert np.all(windows["end_idx"] == [3, 6, 9])
    assert windows["drift_rate"][0] == pytest.approx(0.5)


def test_nan_and_inf_raise_instead_of_silent_metrics():
    gt = make_poses([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    est = gt.copy()
    est[1, 1] = np.nan
    axis = np.asarray([[1.0, 0.0, 0.0], [np.inf, 0.0, 0.0]], dtype=float)

    with pytest.raises(ValueError):
        compute_ATE(est, gt)
    with pytest.raises(ValueError):
        compute_axis_error(gt, gt, axis)


def test_metrics_module_does_not_depend_on_toy_lio_or_day7_summary():
    source = (ROOT / "src/eval/metrics.py").read_text(encoding="utf-8").lower()

    assert "toy_lio" not in source
    assert "day07_toy_lio_summary" not in source
    assert "pose_est_toy" not in source


def test_day8_summary_matches_recomputed_tum_errors(tmp_path):
    module = load_eval_script()
    sequence_dir = ROOT / "data/minibench/ST-L3-S01-M1"
    odi_path = ROOT / "results/day14/raw/ST-L3-S01-M1_odi.csv"
    est_path = ROOT / "results/day14/raw/ST-L3-S01-M1_pose_est_toy.tum"
    out_path = tmp_path / "ST-L3-S01-M1_metrics.csv"

    summary = module.evaluate_sequence(
        sequence_dir,
        odi_path,
        est_path,
        out_path,
        {"window_size": 20, "window_stride": 5},
    )

    gt = load_tum_pose(sequence_dir / "gt.tum")
    est = align_se3_if_needed(load_tum_pose(est_path), gt)
    axis = load_axis_csv(sequence_dir / "axis.csv")
    axis_error = compute_axis_error(est, gt, axis)
    cross_error = compute_cross_error(est, gt, axis)

    assert summary["final_axis_error"] == pytest.approx(float(axis_error[-1]))
    assert summary["final_cross_error"] == pytest.approx(float(cross_error[-1]))
    assert summary["mean_axis_error"] == pytest.approx(float(np.mean(axis_error)))
    assert summary["mean_cross_error"] == pytest.approx(float(np.mean(cross_error)))

    with out_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for field in [
        "start_idx",
        "end_idx",
        "path_length",
        "axis_drift_rate",
        "cross_drift_rate",
        "mean_ODI",
        "median_condition_number",
    ]:
        assert field in rows[0]


def test_cumulative_path_length_is_monotonic():
    gt = make_poses([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [6.0, 8.0, 0.0]])

    path = compute_cumulative_path_length(gt)

    assert np.allclose(path, [0.0, 5.0, 10.0])
    assert np.all(np.diff(path) >= 0.0)


def load_eval_script():
    script_path = ROOT / "scripts/03_eval_metrics.py"
    spec = importlib.util.spec_from_file_location("day8_eval_metrics_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
