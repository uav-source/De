import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_coherent_stress_uses_one_twenty_frame_burst():
    observations = simple_observations(frames=30)
    output = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 3, 4, patch_ids(observations))
    active = np.flatnonzero(np.any(output["contamination_mask"], axis=1))
    assert active.size == 20
    assert np.all(np.diff(active) == 1)
    assert active[0] == int(output["shared_burst_start_frame"])

