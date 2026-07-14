from pathlib import Path

import numpy as np

from minibench.map_lio import run_map_lio
from stage2c_helpers import detector_config, simple_motion, simple_observations, update_config


def test_formal_stage2c_estimator_ignores_gt_fields():
    observations = simple_observations()
    with_gt = dict(observations, pose_gt=np.ones((4, 8)), axis_per_frame=np.ones((4, 3)))
    first = run_map_lio(with_gt, simple_motion(), detector_config(), update_config(), "huber_projected_gain", 0.2, 0.5)
    second = run_map_lio(observations, simple_motion(), detector_config(), update_config(), "huber_projected_gain", 0.2, 0.5)
    assert np.array_equal(first["poses"], second["poses"])
    assert first["frame_diagnostics"] == second["frame_diagnostics"]
    source = (Path(__file__).parents[1] / "src/minibench/map_lio.py").read_text(encoding="utf-8")
    assert 'observations["pose_gt"]' not in source
    assert 'observations["axis_per_frame"]' not in source

