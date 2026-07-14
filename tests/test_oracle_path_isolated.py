import pytest

from minibench.map_lio import run_map_lio
from stage2b_helpers import detector_config, simple_motion, simple_observations, update_config


def test_oracle_direction_is_rejected_for_formal_methods_and_required_for_oracle():
    directions = [[1.0, 0.0, 0.0]] * 4
    with pytest.raises(ValueError, match="isolated"):
        run_map_lio(simple_observations(), simple_motion(), detector_config(), update_config(), "huber_full", 0.2, 0.5, directions)
    with pytest.raises(ValueError, match="oracle_only"):
        run_map_lio(simple_observations(), simple_motion(), detector_config(), update_config(), "huber_oracle_selective", 0.2, 0.5)
