from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.motion_simulator import simulate_motion_measurements  # noqa: E402
from minibench.toy_lio import run_toy_lio  # noqa: E402


CONFIG = ROOT / "configs/detector/odi_default.yaml"


def test_fixed_measurements_make_estimate_independent_of_evaluation_gt(tmp_path, day14_tmp_pipeline):
    sequence_dir = day14_tmp_pipeline["seq"]("ST-L3-S01-M1")
    with np.load(sequence_dir / "observations.npz") as loaded:
        observations = {key: loaded[key].copy() for key in loaded.files}
    motion = simulate_motion_measurements(
        observations["pose_gt"],
        1001,
        {"axis_sigma": 0.004, "cross_sigma": 0.004, "yaw_sigma": 0.0008},
        observations["axis_per_frame"],
    )
    baseline = run_toy_lio(sequence_dir, CONFIG, motion_measurements=motion, observations_path=sequence_dir / "observations.npz")

    observations["pose_gt"] = observations["pose_gt"].copy()
    observations["pose_gt"][:, 1:4] += 1000.0
    modified_path = tmp_path / "modified_gt_observations.npz"
    np.savez_compressed(modified_path, **observations)
    modified = run_toy_lio(sequence_dir, CONFIG, motion_measurements=motion, observations_path=modified_path)
    assert np.allclose(baseline["poses"], modified["poses"])
    assert baseline["summary"] != modified["summary"]


def test_estimator_source_has_no_framewise_gt_delta_or_gt_residual_argument():
    source = (ROOT / "src/minibench/toy_lio.py").read_text(encoding="utf-8")
    assert "gt[idx]" not in source
    assert "gt_delta" not in source
    assert "gt_pose:" not in source
    assert "world_measured" not in source

