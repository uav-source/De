import numpy as np
import pytest

from minibench.map_lio import run_map_lio
from stage2c_helpers import detector_config, simple_motion, simple_observations, update_config


def test_gt_direction_is_isolated_to_offline_oracle_strategy():
    directions = np.tile(np.array([1.0, 0.0, 0.0]), (4, 1))
    with pytest.raises(ValueError, match="isolated"):
        run_map_lio(simple_observations(), simple_motion(), detector_config(), update_config(), "huber_projected_gain", 0.2, 0.5, directions)
    with pytest.raises(ValueError, match="oracle_only"):
        run_map_lio(simple_observations(), simple_motion(), detector_config(), update_config(), "huber_oracle_projected_gain", 0.2, 0.5)
