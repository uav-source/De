from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.odi_tracker import compute_metrics_for_sequence  # noqa: E402


def test_runtime_detector_outputs_do_not_depend_on_gt_axis_or_pose():
    rng = np.random.default_rng(17)
    observations = {
        "timestamps": np.array([0.0, 0.1]),
        "packed_J": rng.normal(size=(2, 64, 6)),
        "R_diag_list": np.full((2, 64), 0.01),
        "axis_per_frame": np.tile([1.0, 0.0, 0.0], (2, 1)),
        "pose_gt": np.zeros((2, 8)),
    }
    config = {
        "s_theta": 0.05,
        "s_p": 0.5,
        "epsilon_mode": "relative_trace",
        "epsilon_ratio": 1.0e-6,
        "translation_schur_damping_ratio": 1.0e-6,
        "tau_w": 0.02,
        "primary_direction_min_eigengap_ratio": 0.02,
        "odi_trigger_threshold": 0.3,
    }
    baseline = compute_metrics_for_sequence(observations, config)
    no_gt = dict(observations)
    no_gt.pop("pose_gt")
    no_gt.pop("axis_per_frame")
    changed = compute_metrics_for_sequence(no_gt, config)
    for field in [
        "ODI_trans",
        "degeneracy_triggered",
        "primary_direction_stable",
        "actionable_direction",
        "primary_weak_dir_x",
        "primary_weak_dir_y",
        "primary_weak_dir_z",
    ]:
        assert np.allclose(baseline[field], changed[field], equal_nan=True)
    assert np.all(np.isnan(changed["primary_direction_axis_alignment"]))
